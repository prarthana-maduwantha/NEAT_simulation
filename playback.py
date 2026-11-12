import math
import os
import pickle
import random
import sys
import neat
import pygame

# Window and simulation constants
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 600
SIM_WIDTH = 800
SIM_HEIGHT = 600
UI_PANEL_WIDTH = 400
FPS = 60

# Colors
WHITE = (255, 255, 255)
CREATURE_COLOR = (52, 152, 219)   # Blue for creatures so green Food stands out
FOOD_GREEN = (46, 204, 113)       # Green square for food
PURPLE = (155, 89, 182)           # Purple square for poison
DARK_GRAY = (40, 40, 40)
YELLOW = (255, 215, 0)
LIGHT_GRAY = (220, 220, 220)
NODE_COLOR = (235, 235, 235)
NODE_BORDER = (20, 20, 20)
WEIGHT_POS = (46, 204, 113)
WEIGHT_NEG = (231, 76, 60)
RED = (231, 76, 60)
BLUE = (0, 150, 255)

# Initialize Pygame and screen
pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("2D Artificial Life Simulation - Champion Playback")
font = pygame.font.SysFont(None, 18)
title_font = pygame.font.SysFont(None, 24)


class Creature:
    """Represents a creature entity in the 2D simulation."""

    def __init__(self, center_x, center_y, size=20, speed=5, color=CREATURE_COLOR):
        self.size = size
        self.rect = pygame.Rect(0, 0, size, size)
        self.rect.center = (center_x, center_y)
        self.speed = speed
        self.color = color
        self.max_energy = 200
        self.energy = 200
        self.alive = True

    @property
    def x(self):
        return self.rect.x

    @x.setter
    def x(self, val):
        self.rect.x = val

    @property
    def y(self):
        return self.rect.y

    @y.setter
    def y(self, val):
        self.rect.y = val

    def move(self, direction):
        """Move the creature based on direction index (0: Up, 1: Down, 2: Left, 3: Right)."""
        if direction == 0:  # Up
            self.rect.y -= self.speed
        elif direction == 1:  # Down
            self.rect.y += self.speed
        elif direction == 2:  # Left
            self.rect.x -= self.speed
        elif direction == 3:  # Right
            self.rect.x += self.speed

    def respawn(self):
        """Reset creature inside the central safe zone with full energy."""
        self.rect.center = (random.randint(300, 500), random.randint(200, 400))
        self.energy = self.max_energy
        self.alive = True

    def draw(self, surface):
        """Render the creature on the provided surface."""
        pygame.draw.rect(surface, self.color, self.rect)


class Food:
    """Represents a food item (Green square) that creatures consume."""

    def __init__(self, size=10, color=FOOD_GREEN):
        self.size = size
        self.color = color
        self.rect = pygame.Rect(0, 0, size, size)
        self.respawn()

    def respawn(self):
        """Reposition the food within the simulation area with a 50-pixel padding from walls."""
        self.rect.x = random.randint(50, 750)
        self.rect.y = random.randint(50, 550)

    def draw(self, surface):
        """Render the food item on the provided surface."""
        pygame.draw.rect(surface, self.color, self.rect)


class Poison:
    """Represents a poison hazard (Purple square) that kills creatures upon contact."""

    def __init__(self, size=10, color=PURPLE):
        self.size = size
        self.color = color
        self.rect = pygame.Rect(0, 0, size, size)
        self.respawn()

    def respawn(self):
        """Reposition the poison within the simulation area with a 50-pixel padding from walls."""
        self.rect.x = random.randint(50, 750)
        self.rect.y = random.randint(50, 550)

    def draw(self, surface):
        """Render the poison on the provided surface."""
        pygame.draw.rect(surface, self.color, self.rect)


class Wolf:
    """Represents an active predator that hunts the nearest creature."""

    def __init__(self, center_x=None, center_y=None, size=15, speed=3, color=RED):
        self.size = size
        self.rect = pygame.Rect(0, 0, size, size)
        self.base_speed = 3
        self.sprint_speed = 6
        self.speed = self.base_speed
        self.color = color

        # Stamina and resting state
        self.stamina = 100.0
        self.max_stamina = 100.0
        self.is_resting = False

        if center_x is not None and center_y is not None:
            self.rect.center = (center_x, center_y)
            self.clamp_to_bounds()
            self.exact_x = float(self.rect.centerx)
            self.exact_y = float(self.rect.centery)
        else:
            self.respawn()

    def clamp_to_bounds(self):
        """Keep wolf within playable 800x600 boundaries."""
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > SIM_WIDTH:
            self.rect.right = SIM_WIDTH
        if self.rect.top < 0:
            self.rect.top = 0
        if self.rect.bottom > SIM_HEIGHT:
            self.rect.bottom = SIM_HEIGHT

    def respawn(self):
        """Spawns or resets the wolf at a random edge of the screen (Top, Bottom, Left, or Right)."""
        edge = random.choice(["Top", "Bottom", "Left", "Right"])
        if edge == "Top":
            self.rect.center = (random.randint(0, 800), 0)
        elif edge == "Bottom":
            self.rect.center = (random.randint(0, 800), 600)
        elif edge == "Left":
            self.rect.center = (0, random.randint(0, 600))
        elif edge == "Right":
            self.rect.center = (800, random.randint(0, 600))

        self.clamp_to_bounds()
        self.exact_x = float(self.rect.centerx)
        self.exact_y = float(self.rect.centery)
        self.stamina = self.max_stamina
        self.is_resting = False

    @property
    def x(self):
        return self.rect.x

    @x.setter
    def x(self, val):
        self.rect.x = val
        self.exact_x = float(self.rect.centerx)

    @property
    def y(self):
        return self.rect.y

    @y.setter
    def y(self, val):
        self.rect.y = val
        self.exact_y = float(self.rect.centery)

    def chase(self, creatures):
        """Hunts the closest creature with dynamic stamina and sprinting mechanics."""
        if not creatures:
            return

        target_creature = min(
            creatures,
            key=lambda c: (c.rect.centerx - self.rect.centerx) ** 2 + (c.rect.centery - self.rect.centery) ** 2,
        )
        dx = target_creature.rect.centerx - self.rect.centerx
        dy = target_creature.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)

        # Resting recovery
        if self.is_resting:
            self.speed = 0
            self.stamina = min(self.max_stamina, self.stamina + 1.0)
            if self.stamina >= self.max_stamina:
                self.is_resting = False
            return

        # Distance-based speed selection
        if dist < 150:
            self.speed = self.sprint_speed
            self.stamina -= 2.0
        else:
            self.speed = self.base_speed
            self.stamina = min(self.max_stamina, self.stamina + 0.5)

        # Exhaustion check
        if self.stamina <= 0:
            self.stamina = 0.0
            self.is_resting = True

        # Move smoothly towards target
        if dist > 0 and self.speed > 0:
            move_step = min(float(self.speed), dist)
            self.exact_x += (dx / dist) * move_step
            self.exact_y += (dy / dist) * move_step
            self.rect.center = (int(round(self.exact_x)), int(round(self.exact_y)))

    def draw(self, surface):
        """Render the wolf on the provided surface."""
        pygame.draw.rect(surface, self.color, self.rect)


def draw_network(surface, genome, start_x, start_y):
    """Renders the neural network architecture of a genome on the UI panel."""
    node_positions = {}

    # Hardcoded positions for 10 input nodes on the left side of UI panel
    input_keys = [-1, -2, -3, -4, -5, -6, -7, -8, -9, -10]
    for idx, k in enumerate(input_keys):
        node_positions[k] = (start_x + 70, start_y + 80 + idx * 42)

    # Hardcoded positions for 4 output nodes on the right side of UI panel
    node_positions[0] = (start_x + 330, start_y + 130)
    node_positions[1] = (start_x + 330, start_y + 220)
    node_positions[2] = (start_x + 330, start_y + 310)
    node_positions[3] = (start_x + 330, start_y + 400)

    # Hidden nodes in middle
    hidden_nodes = [k for k in genome.nodes.keys() if k not in (0, 1, 2, 3)]
    if hidden_nodes:
        step_y = 330 / (len(hidden_nodes) + 1)
        for idx, h_id in enumerate(hidden_nodes):
            node_positions[h_id] = (start_x + 200, int(start_y + 110 + (idx + 1) * step_y))

    # Panel Title
    title_surf = title_font.render("CHAMPION NEURAL NETWORK", True, LIGHT_GRAY)
    surface.blit(title_surf, (start_x + (UI_PANEL_WIDTH - title_surf.get_width()) // 2, start_y + 20))

    # Draw connection lines
    for cg in genome.connections.values():
        if cg.enabled:
            in_node, out_node = cg.key
            if in_node in node_positions and out_node in node_positions:
                start_pos = node_positions[in_node]
                end_pos = node_positions[out_node]
                color = WEIGHT_POS if cg.weight > 0 else WEIGHT_NEG
                thickness = max(1, min(int(abs(cg.weight) * 2.5), 8))
                pygame.draw.line(surface, color, start_pos, end_pos, thickness)

    # Labels for inputs and outputs
    labels = {
        -1: "F_dx",
        -2: "F_dy",
        -3: "P_dx",
        -4: "P_dy",
        -5: "W_dx",
        -6: "W_dy",
        -7: "W_top",
        -8: "W_bot",
        -9: "W_lft",
        -10: "W_rgt",
        0: "Up",
        1: "Down",
        2: "Left",
        3: "Right",
    }

    for node_id, pos in node_positions.items():
        radius = 9 if node_id < 0 else 12
        pygame.draw.circle(surface, NODE_COLOR, pos, radius)
        pygame.draw.circle(surface, NODE_BORDER, pos, radius, 2)
        label_text = labels.get(node_id, f"H{node_id}")
        txt_surf = font.render(label_text, True, LIGHT_GRAY)
        if node_id < 0:
            surface.blit(txt_surf, (pos[0] - txt_surf.get_width() - 14, pos[1] - txt_surf.get_height() // 2))
        elif node_id in (0, 1, 2, 3):
            surface.blit(txt_surf, (pos[0] + 16, pos[1] - txt_surf.get_height() // 2))
        else:
            surface.blit(txt_surf, (pos[0] - txt_surf.get_width() // 2, pos[1] - 22))


def main():
    """Continuous, infinite showcase loop running the trained champion genome."""
    local_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(local_dir, "config.txt")
    dna_path = os.path.join(local_dir, "best_dna.pkl")

    if not os.path.exists(dna_path):
        print(f"Error: Champion file '{dna_path}' not found! Run main.py first to evolve and save best_dna.pkl.")
        sys.exit(1)

    # Load configuration
    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        config_path,
    )

    # Load champion genome using pickle
    with open(dna_path, "rb") as f:
        loaded_genome = pickle.load(f)

    # Recreate the neural network of the ultimate survivor
    net = neat.nn.FeedForwardNetwork.create(loaded_genome, config)

    clock = pygame.time.Clock()

    # Initialize exactly ONE of each entity inside the Safe Zone
    creature = Creature(
        center_x=random.randint(300, 500), center_y=random.randint(200, 400)
    )
    food = Food()
    poison = Poison()
    wolf = Wolf()

    score = 0
    deaths = 0
    last_event = "Simulation Started"
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # 1. Raw distances to Food, Poison, and Wolf
        raw_food_dx = food.rect.centerx - creature.rect.centerx
        raw_food_dy = food.rect.centery - creature.rect.centery
        raw_poison_dx = poison.rect.centerx - creature.rect.centerx
        raw_poison_dy = poison.rect.centery - creature.rect.centery
        raw_dist_x_wolf = wolf.rect.centerx - creature.rect.centerx
        raw_dist_y_wolf = wolf.rect.centery - creature.rect.centery

        # Fog of War: 200-pixel sight radius
        SIGHT_RADIUS = 200.0
        dist_to_food = math.hypot(raw_food_dx, raw_food_dy)
        dist_to_poison = math.hypot(raw_poison_dx, raw_poison_dy)
        dist_to_wolf = math.hypot(raw_dist_x_wolf, raw_dist_y_wolf)

        # If beyond 200px sight radius, pass 0 for that target's coordinates
        food_dx = raw_food_dx if dist_to_food <= SIGHT_RADIUS else 0.0
        food_dy = raw_food_dy if dist_to_food <= SIGHT_RADIUS else 0.0
        poison_dx = raw_poison_dx if dist_to_poison <= SIGHT_RADIUS else 0.0
        poison_dy = raw_poison_dy if dist_to_poison <= SIGHT_RADIUS else 0.0
        dist_x_wolf = raw_dist_x_wolf if dist_to_wolf <= SIGHT_RADIUS else 0.0
        dist_y_wolf = raw_dist_y_wolf if dist_to_wolf <= SIGHT_RADIUS else 0.0

        # Cap distance values at 200 to prevent neural network saturation
        food_dx = max(-200.0, min(200.0, float(food_dx)))
        food_dy = max(-200.0, min(200.0, float(food_dy)))
        poison_dx = max(-200.0, min(200.0, float(poison_dx)))
        poison_dy = max(-200.0, min(200.0, float(poison_dy)))
        dist_x_wolf = max(-200.0, min(200.0, float(dist_x_wolf)))
        dist_y_wolf = max(-200.0, min(200.0, float(dist_y_wolf)))

        # 2. Wall distance senses (800x600 playable area, capped at max 200)
        dist_top = min(float(creature.y), 200.0)
        dist_bottom = min(float(SIM_HEIGHT - creature.y), 200.0)
        dist_left = min(float(creature.x), 200.0)
        dist_right = min(float(SIM_WIDTH - creature.x), 200.0)

        # 3. Pass 10 senses into the champion neural network
        all_inputs = (
            food_dx,
            food_dy,
            poison_dx,
            poison_dy,
            dist_x_wolf,
            dist_y_wolf,
            dist_top,
            dist_bottom,
            dist_left,
            dist_right,
        )
        expected_in = len(net.input_nodes)
        output = net.activate(all_inputs[:expected_in])

        # 4. Apply output to creature's movement (0: Up, 1: Down, 2: Left, 3: Right)
        max_val = max(output)
        best_indices = [idx for idx, val in enumerate(output) if abs(val - max_val) < 1e-5]
        decision = random.choice(best_indices) if len(best_indices) > 1 else best_indices[0]
        creature.move(decision)

        # Wolf hunts the creature
        wolf.chase([creature])

        # Creature energy depletion
        creature.energy -= 1

        # Check death conditions (Starvation, Lethal Walls, Poison, Wolf)
        died = False
        death_cause = ""

        # 1. Starvation
        if creature.energy <= 0:
            died = True
            death_cause = "Starvation"

        # 2. Lethal wall collision
        if (
            creature.rect.left < 0
            or creature.rect.right > SIM_WIDTH
            or creature.rect.top < 0
            or creature.rect.bottom > SIM_HEIGHT
        ):
            died = True
            death_cause = "Lethal Wall"

        # 3. Poison collision
        if creature.rect.colliderect(poison.rect):
            died = True
            death_cause = "Poison"

        # 4. Wolf collision
        if creature.rect.colliderect(wolf.rect):
            died = True
            death_cause = "Wolf"

        # Respawn creature in center and reset Food/Poison on death
        if died:
            deaths += 1
            last_event = f"Died ({death_cause})"
            creature.respawn()
            food.respawn()
            poison.respawn()

            # Prevent immediate re-catch if wolf is camping near the center
            if math.hypot(wolf.rect.centerx - SIM_WIDTH // 2, wolf.rect.centery - SIM_HEIGHT // 2) < 80:
                wolf.respawn()

        # Food consumption
        if creature.rect.colliderect(food.rect):
            score += 1
            creature.energy = min(creature.max_energy, creature.energy + 80)
            food.respawn()
            last_event = "Ate Food (+80 Energy)"

        # ----------------- RENDERING -----------------
        screen.fill(WHITE)

        # Draw entities
        food.draw(screen)
        poison.draw(screen)
        wolf.draw(screen)

        # Wolf stamina bar
        stamina_bar_width = max(0, int((wolf.stamina / wolf.max_stamina) * wolf.rect.width))
        wolf_bar_x = wolf.rect.x
        wolf_bar_y = max(0, wolf.rect.y - 6)
        pygame.draw.rect(screen, (180, 180, 180), (wolf_bar_x, wolf_bar_y, wolf.rect.width, 3))
        if stamina_bar_width > 0:
            pygame.draw.rect(screen, BLUE, (wolf_bar_x, wolf_bar_y, stamina_bar_width, 3))

        # Creature rendering with yellow alpha ring
        creature.draw(screen)
        pygame.draw.circle(screen, YELLOW, creature.rect.center, radius=18, width=2)

        # Creature health bar
        bar_color = FOOD_GREEN if creature.energy >= 50 else RED
        bar_width = max(0, int((creature.energy / creature.max_energy) * creature.rect.width))
        bar_x = creature.rect.x
        bar_y = max(0, creature.rect.y - 6)
        pygame.draw.rect(screen, (180, 180, 180), (bar_x, bar_y, creature.rect.width, 3))
        if bar_width > 0:
            pygame.draw.rect(screen, bar_color, (bar_x, bar_y, bar_width, 3))

        # Sensory tracking debug lines & Fog of War circle
        line_overlay = pygame.Surface((SIM_WIDTH, SIM_HEIGHT), pygame.SRCALPHA)
        c_pos = creature.rect.center

        pygame.draw.circle(line_overlay, (200, 200, 200, 50), c_pos, int(SIGHT_RADIUS), width=1)
        if math.hypot(food.rect.centerx - c_pos[0], food.rect.centery - c_pos[1]) <= SIGHT_RADIUS:
            pygame.draw.aaline(line_overlay, (46, 204, 113, 160), c_pos, food.rect.center)
        if math.hypot(poison.rect.centerx - c_pos[0], poison.rect.centery - c_pos[1]) <= SIGHT_RADIUS:
            pygame.draw.aaline(line_overlay, (155, 89, 182, 160), c_pos, poison.rect.center)
        if math.hypot(wolf.rect.centerx - c_pos[0], wolf.rect.centery - c_pos[1]) <= SIGHT_RADIUS:
            pygame.draw.aaline(line_overlay, (231, 76, 60, 160), c_pos, wolf.rect.center)
        screen.blit(line_overlay, (0, 0))

        # UI Panel (right 400x600)
        pygame.draw.rect(screen, DARK_GRAY, (SIM_WIDTH, 0, UI_PANEL_WIDTH, WINDOW_HEIGHT))

        # Render champion neural network architecture
        draw_network(screen, loaded_genome, start_x=SIM_WIDTH, start_y=0)

        # Separator line above stats
        pygame.draw.line(screen, (70, 70, 70), (SIM_WIDTH + 20, 500), (WINDOW_WIDTH - 20, 500), 1)

        # UI Telemetry Stats
        wolf_state = "Resting" if wolf.is_resting else ("Sprinting" if wolf.speed > wolf.base_speed else "Cruising")
        stats_lines = [
            f"Food Eaten: {score}   |   Deaths: {deaths}",
            f"Energy: {max(0, creature.energy)}/{creature.max_energy}   |   Wolf Stamina: {int(wolf.stamina)}%",
            f"Wolf State: {wolf_state}   |   {last_event}",
        ]
        for idx, line in enumerate(stats_lines):
            line_surf = font.render(line, True, LIGHT_GRAY)
            screen.blit(line_surf, (SIM_WIDTH + 30, 515 + idx * 24))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
