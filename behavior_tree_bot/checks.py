

def if_neutral_planet_available(state):
    return any(state.neutral_planets())


def have_largest_fleet(state):
    return sum(planet.num_ships for planet in state.my_planets()) \
             + sum(fleet.num_ships for fleet in state.my_fleets()) \
           > sum(planet.num_ships for planet in state.enemy_planets()) \
             + sum(fleet.num_ships for fleet in state.enemy_fleets())

def if_enemy_planet_available(state):
    return any(state.enemy_planets())

def is_any_planet_under_threat(state):
    for planet in state.my_planets():
        incoming_enemy = [f for f in state.enemy_fleets() if f.destination_planet == planet.ID]
        if not incoming_enemy:
            continue
        total_incoming = sum(f.num_ships for f in incoming_enemy)
        soonest_arrival = min(f.turns_remaining for f in incoming_enemy)
        projected_defense = planet.num_ships + planet.growth_rate * soonest_arrival
        if total_incoming > projected_defense:
            return True
    return False

