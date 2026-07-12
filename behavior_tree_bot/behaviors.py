import sys
sys.path.insert(0, '../')
from planet_wars import issue_order

# Helper Functions -------------------------------------------------------------------------
def already_targeted_by_me(state, planet_id):
    # This keeps us from sending two random fleets to the same planet for no reason.
    # Of course, it's not always bad to double-send, but in our case, it feels wasteful.
    # Will see how this performs
    return any(fleet.destination_planet == planet_id for fleet in state.my_fleets())


def reserve_ships(planet):
    # Will leave some ships behind so we do not immediately lose the source planet.
    # The 25% is essentially a safety cushion.
    return max(1, int(planet.num_ships * 0.25))


def available_ships(planet):
    # Ships we are willing to use from this planet right now.
    # It can be zero if the planet is already pretty weak.
    return max(0, int(planet.num_ships) - reserve_ships(planet))


def ships_needed_to_capture(state, source, target):
    # For Neutral planets, we just need to beat their current ships.
    if target.owner == 0:
        return int(target.num_ships) + 1

    # Enemy planets grow while our fleet travels there, so we estimate how many
    # ships they will have by the time we arrive. I feel like this is better than
    # attacking using only the current ship count.
    distance = state.distance(source.ID, target.ID)
    return int(target.num_ships + (target.growth_rate * distance)) + 1


def best_source_for_target(state, target):
    # Find one of our planets that can actually afford this attack/expansion.
    # Sorting by distance first makes sense to me since closer fleets arrive faster.
    choices = []

    for source in state.my_planets():
        ships_needed = ships_needed_to_capture(state, source, target)
        usable_ships = available_ships(source)

        if usable_ships >= ships_needed:
            distance = state.distance(source.ID, target.ID)
            choices.append((distance, -usable_ships, source, ships_needed))

    if not choices:
        return None, 0

    choices.sort()
    best_choice = choices[0]
    return best_choice[2], best_choice[3]


def neutral_planet_score(state, planet):
    # The lower the score, the better. This makes the bot like planets that are close
    # and have a higher growth rate.
    my_planets = state.my_planets()
    if not my_planets:
        return float('inf')

    closest_distance = min(state.distance(source.ID, planet.ID) for source in my_planets)
    return (planet.num_ships + closest_distance) / max(1, planet.growth_rate)


def enemy_planet_score(state, planet):
    # Lower score is better here too. We still like weak planets, but
    # growth rate matters because stealing a high-growth enemy planet is actually useful.
    my_planets = state.my_planets()
    if not my_planets:
        return float('inf')

    closest_distance = min(state.distance(source.ID, planet.ID) for source in my_planets)
    return (planet.num_ships + closest_distance) / max(1, planet.growth_rate)

# End of Helper Functions -----------------------------------------------------------------------


def attack_weakest_enemy_planet(state):
    # Used a different strategy. It estimates how many ships are needed and only attacks
    # if the move is legal.
    enemy_targets = [
        planet for planet in state.enemy_planets()
        if not already_targeted_by_me(state, planet.ID)
    ]

    if not enemy_targets:
        return False

    def get_enemy_score(planet):
        return enemy_planet_score(state, planet)

    enemy_targets.sort(key=get_enemy_score)

    orders_sent = 0
    max_orders_this_turn = 2

    for target in enemy_targets:
        if orders_sent >= max_orders_this_turn:
            break

        source, ships_needed = best_source_for_target(state, target)
        if source is None:
            continue

        if issue_order(state, source.ID, target.ID, ships_needed):
            orders_sent += 1

    return orders_sent > 0


def spread_to_weakest_neutral_planet(state):
    # Also optimized. Instead of literally grabbing only the weakest neutral planet,
    # it tries to pick neutral planets that are cheap, close, and actually worth owning.
    neutral_targets = [
        planet for planet in state.neutral_planets()
        if not already_targeted_by_me(state, planet.ID)
    ]

    if not neutral_targets:
        return False

    def get_neutral_score(planet):
        return neutral_planet_score(state, planet)

    neutral_targets.sort(key=get_neutral_score)

    orders_sent = 0
    max_orders_this_turn = 2

    for target in neutral_targets:
        if orders_sent >= max_orders_this_turn:
            break

        source, ships_needed = best_source_for_target(state, target)
        if source is None:
            continue

        if issue_order(state, source.ID, target.ID, ships_needed):
            orders_sent += 1

    return orders_sent > 0


def defend_threatened_planet(state):
    # This is here in case the tree uses the threat check later.
    # It looks for one of our planets that is probably going to lose to an
    # incoming enemy fleet, then sends help from another planet if possible.
    threatened_planets = []

    for planet in state.my_planets():
        incoming_enemy = [
            fleet for fleet in state.enemy_fleets()
            if fleet.destination_planet == planet.ID
        ]

        if not incoming_enemy:
            continue

        # This is a rough estimate. It groups enemy fleets together, which is definitely
        # NOT perfect, but should work for a defensive behavior.
        soonest_arrival = min(fleet.turns_remaining for fleet in incoming_enemy)
        total_enemy_ships = sum(fleet.num_ships for fleet in incoming_enemy)
        projected_ships = planet.num_ships + (planet.growth_rate * soonest_arrival)
        ships_needed = int(total_enemy_ships - projected_ships) + 1

        if ships_needed > 0:
            threatened_planets.append((ships_needed, soonest_arrival, planet))

    if not threatened_planets:
        return False

    def get_threat_priority(item):
        ships_needed = item[0]
        arrival_time = item[1]
        return (ships_needed, arrival_time)

    # Defend the planet that needs the least help first, since it is the easiest save.
    threatened_planets.sort(key=get_threat_priority)

    for ships_needed, arrival_time, target in threatened_planets:
        helper_planets = [
            planet for planet in state.my_planets()
            if planet.ID != target.ID
        ]

        # This replaces: key=lambda planet: state.distance(planet.ID, target.ID)
        def get_distance_to_target(planet):
            return state.distance(planet.ID, target.ID)

        helper_planets.sort(key=get_distance_to_target)

        for source in helper_planets:
            # If help gets there after the enemy, it probably does not help much.
            if state.distance(source.ID, target.ID) > arrival_time:
                continue

            if available_ships(source) >= ships_needed:
                return issue_order(state, source.ID, target.ID, ships_needed)

    return False