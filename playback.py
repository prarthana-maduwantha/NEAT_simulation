import math
import os
import random
import sys
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
pygame.display.set_caption("2D Artificial Life Simulation - Playback")
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
        """Reset creature to center of simulation field with full energy."""
        self.rect.center = (SIM_WIDTH // 2, SIM_HEIGHT // 2)
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
        """Instantly reposition the food within the 800x600 simulation area."""
        self.rect.x = random.randint(0, SIM_WIDTH - self.size)
        self.rect.y = random.randint(0, SIM_HEIGHT - self.size)

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
        """Instantly reposition the poison within the 800x600 simulation area."""
        self.rect.x = random.randint(0, SIM_WIDTH - self.size)
        self.rect.y = random.randint(0, SIM_HEIGHT - self.size)

    def draw(self, surface):
        """Render the poison on the provided surface."""
        pygame.draw.rect(surface, self.color, self.rect)


class Wolf:
    """Represents an active predator that hunts the nearest creature."""

    def __init__(self, center_x=None, center_y=None, size=15, speed=3, color=RED):
        if center_x is None:
            center_x = random.randint(size, SIM_WIDTH - size)
        if center_y is None:
            center_y = random.randint(size, SIM_HEIGHT - size)

        self.size = size
        self.rect = pygame.Rect(0, 0, size, size)
        self.rect.center = (center_x, center_y)
        self.exact_x = float(self.rect.centerx)
        self.exact_y = float(self.rect.centery)
        self.base_speed = 3
        self.sprint_speed = 6
        self.speed = self.base_speed
        self.color = color

        # Stamina and resting state
        self.stamina = 100.0
        self.max_stamina = 100.0
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

    # Positions for 10 input nodes
    input_keys = [-1, -2, -3, -4, -5, -6, -7, -8, -9, -10]
    for idx, k in enumerate(input_keys):
        node_positions[k] = (start_x + 70, start_y + 85 + idx * 47)

    # Positions for 4 output nodes
    node_positions[0] = (start_x + 330, start_y + 150)
    node_positions[1] = (start_x + 330, start_y + 250)
    node_positions[2] = (start_x + 330, start_y + 350)
    node_positions[3] = (start_x + 330, start_y + 450)

    # Hidden nodes in middle
    hidden_nodes = [k for k in genome.nodes.keys() if k not in (0, 1, 2, 3)]
    if hidden_nodes:
        step_y = 360 / (len(hidden_nodes) + 1)
        for idx, h_id in enumerate(hidden_nodes):
            node_positions[h_id] = (start_x + 200, int(start_y + 120 + (idx + 1) * step_y))

    # Panel Title
    title_surf = title_font.render("PLAYBACK NEURAL NETWORK", True, LIGHT_GRAY)
    surface.blit(title_surf, (start_x + 75, start_y + 20))

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

    # Labels
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
            surface.blit(txt_surf, (pos[0] - txt_surf.get_width() // 2, pos[1] - 24))


def main():
    """Continuous, infinite simulation loop with exactly ONE Creature, ONE Wolf, ONE Food, and ONE Poison."""
    clock = pygame.time.Clock()

    # Initialize exactly ONE of each entity
    creature = Creature(center_x=SIM_WIDTH // 2, center_y=SIM_HEIGHT // 2)
    food = Food()
    poison = Poison()
    wolf = Wolf(center_x=30, center_y=30)

    score = 0
    deaths = 0
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Wolf hunts the creature
        wolf.chase([creature])

        # Creature energy depletion
        creature.energy -= 1

        # Check death conditions (Starvation, Lethal Walls, Poison, Wolf)
        died = False

        # 1. Starvation
        if creature.energy <= 0:
            died = True

        # 2. Out-of-bounds wall collision
        if (
            creature.rect.left < 0
            or creature.rect.right > SIM_WIDTH
            or creature.rect.top < 0
            or creature.rect.bottom > SIM_HEIGHT
        ):
            died = True

        # 3. Poison collision
        if creature.rect.colliderect(poison.rect):
            poison.respawn()
            died = True

        # 4. Wolf collision
        if creature.rect.colliderect(wolf.rect):
            died = True

        # Respawn creature on death to keep simulation infinite
        if died:
            deaths += 1
            creature.respawn()

        # Food consumption
        if creature.rect.colliderect(food.rect):
            score += 1
            creature.energy = min(creature.max_energy, creature.energy + 80)
            food.respawn()

        # Rendering
        screen.fill(WHITE)

        # Simulation field
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

        # Creature rendering
        creature.draw(screen)

        # Creature health bar
        bar_color = FOOD_GREEN if creature.energy >= 50 else RED
        bar_width = max(0, int((creature.energy / creature.max_energy) * creature.rect.width))
        bar_x = creature.rect.x
        bar_y = max(0, creature.rect.y - 6)
        pygame.draw.rect(screen, (180, 180, 180), (bar_x, bar_y, creature.rect.width, 3))
        if bar_width > 0:
            pygame.draw.rect(screen, bar_color, (bar_x, bar_y, bar_width, 3))

        # Sensory tracking debug lines & Fog of War
        line_overlay = pygame.Surface((SIM_WIDTH, SIM_HEIGHT), pygame.SRCALPHA)
        c_pos = creature.rect.center
        SIGHT_RADIUS = 200.0

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

        # UI Stats
        title_surf = title_font.render("PLAYBACK SIMULATION", True, LIGHT_GRAY)
        screen.blit(title_surf, (SIM_WIDTH + 85, 30))

        stats_lines = [
            f"Food Eaten: {score}",
            f"Deaths: {deaths}",
            f"Creature Energy: {max(0, creature.energy)} / {creature.max_energy}",
            f"Wolf Stamina: {int(wolf.stamina)} / {int(wolf.max_stamina)}",
            f"Wolf State: {'Resting' if wolf.is_resting else ('Sprinting' if wolf.speed > wolf.base_speed else 'Cruising')}",
        ]
        for idx, line in enumerate(stats_lines):
            line_surf = font.render(line, True, LIGHT_GRAY)
            screen.blit(line_surf, (SIM_WIDTH + 80, 90 + idx * 30))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
