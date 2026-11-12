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
RENDER_MODE = True

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

# Ensure checkpoints directory exists
os.makedirs("checkpoints", exist_ok=True)

# Initialize Pygame and screen
pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("2D Artificial Life Simulation")
font = pygame.font.SysFont(None, 18)
title_font = pygame.font.SysFont(None, 24)

# Global tracker for champion genome across all generations
best_genome_overall = None


class Creature:
    """Represents a creature entity in the 2D simulation."""

    def __init__(self, center_x, center_y, size=20, speed=5, color=CREATURE_COLOR):
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

    def draw(self, surface):
        """Render the creature on the provided surface."""
        pygame.draw.rect(surface, self.color, self.rect)


class Food:
    """Represents a food item (Green square) that creatures consume for energy/fitness."""

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

        # 1. Find the closest creature and calculate geometric distance
        target_creature = min(
            creatures,
            key=lambda c: (c.rect.centerx - self.rect.centerx) ** 2 + (c.rect.centery - self.rect.centery) ** 2,
        )
        dx = target_creature.rect.centerx - self.rect.centerx
        dy = target_creature.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)

        # 2. If self.is_resting is True: speed is 0. Increase self.stamina by 1 per frame.
        if self.is_resting:
            self.speed = 0
            self.stamina = min(self.max_stamina, self.stamina + 1.0)
            if self.stamina >= self.max_stamina:
                self.is_resting = False
            return

        # 3. If self.is_resting is False: Check distance to target
        if dist < 150:
            # Sprint mode: move at sprint_speed and decrease stamina by 2 per frame
            self.speed = self.sprint_speed
            self.stamina -= 2.0
        else:
            # Cruise mode: move at base_speed and regenerate stamina by 0.5 per frame
            self.speed = self.base_speed
            self.stamina = min(self.max_stamina, self.stamina + 0.5)

        # 4. If self.stamina <= 0 at any point, set self.is_resting = True
        if self.stamina <= 0:
            self.stamina = 0.0
            self.is_resting = True

        # Move towards target at self.speed
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
        node_positions[k] = (start_x + 70, start_y + 85 + idx * 47)

    # Hardcoded positions for 4 output nodes on the right side of UI panel
    # 0: Up, 1: Down, 2: Left, 3: Right
    node_positions[0] = (start_x + 330, start_y + 150)
    node_positions[1] = (start_x + 330, start_y + 250)
    node_positions[2] = (start_x + 330, start_y + 350)
    node_positions[3] = (start_x + 330, start_y + 450)

    # Dynamically calculate positions for any hidden nodes in the middle
    hidden_nodes = [k for k in genome.nodes.keys() if k not in (0, 1, 2, 3)]
    if hidden_nodes:
        step_y = 360 / (len(hidden_nodes) + 1)
        for idx, h_id in enumerate(hidden_nodes):
            node_positions[h_id] = (start_x + 200, int(start_y + 120 + (idx + 1) * step_y))

    # Panel Title
    title_surf = title_font.render("ALPHA NEURAL NETWORK", True, LIGHT_GRAY)
    surface.blit(title_surf, (start_x + 85, start_y + 20))

    # Draw connection lines
    for cg in genome.connections.values():
        if cg.enabled:
            in_node, out_node = cg.key
            if in_node in node_positions and out_node in node_positions:
                start_pos = node_positions[in_node]
                end_pos = node_positions[out_node]

                # Green if weight > 0, Red if weight < 0
                color = WEIGHT_POS if cg.weight > 0 else WEIGHT_NEG

                # Thickness proportional to absolute value of the weight
                thickness = max(1, min(int(abs(cg.weight) * 2.5), 8))

                pygame.draw.line(surface, color, start_pos, end_pos, thickness)

    # Draw node circles and text labels
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
        # Node circle and outline
        radius = 9 if node_id < 0 else 12
        pygame.draw.circle(surface, NODE_COLOR, pos, radius)
        pygame.draw.circle(surface, NODE_BORDER, pos, radius, 2)

        # Labels
        label_text = labels.get(node_id, f"H{node_id}")
        txt_surf = font.render(label_text, True, LIGHT_GRAY)
        if node_id < 0:
            surface.blit(txt_surf, (pos[0] - txt_surf.get_width() - 14, pos[1] - txt_surf.get_height() // 2))
        elif node_id in (0, 1, 2, 3):
            surface.blit(txt_surf, (pos[0] + 16, pos[1] - txt_surf.get_height() // 2))
        else:
            surface.blit(txt_surf, (pos[0] - txt_surf.get_width() // 2, pos[1] - 24))


def eval_genomes(genomes, config):
    """Evaluates the fitness of each genome in the population over a simulation generation."""
    global RENDER_MODE
    nets = []
    ge = []
    creatures = []

    # Initialize neural network, genome fitness, and creature instance for each genome
    for genome_id, genome in genomes:
        net = neat.nn.FeedForwardNetwork.create(genome, config)
        nets.append(net)
        genome.fitness = 0
        ge.append(genome)
        # Scatter creatures randomly inside central "Safe Zone" to give diverse starting scenarios
        spawn_x = random.randint(300, 500)
        spawn_y = random.randint(200, 400)
        creatures.append(Creature(center_x=spawn_x, center_y=spawn_y))

    food = Food()
    poison = Poison()
    # Spawn one Wolf at a random edge of the screen before the generation starts
    edge = random.choice(["Top", "Bottom", "Left", "Right"])
    if edge == "Top":
        wolf = Wolf(center_x=random.randint(0, 800), center_y=0)
    elif edge == "Bottom":
        wolf = Wolf(center_x=random.randint(0, 800), center_y=600)
    elif edge == "Left":
        wolf = Wolf(center_x=0, center_y=random.randint(0, 600))
    elif edge == "Right":
        wolf = Wolf(center_x=800, center_y=random.randint(0, 600))
    clock = pygame.time.Clock()
    running = True
    frame_counter = 0

    while running and len(creatures) > 0:
        frame_counter += 1
        if frame_counter > 1000:
            break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    RENDER_MODE = not RENDER_MODE
                    print(f"RENDER_MODE: {RENDER_MODE}")

        # Update wolf position chasing nearest survivor every frame
        wolf.chase(creatures)

        # Update each creature via its neural network (iterate in reverse for safe popping)
        for i in range(len(creatures) - 1, -1, -1):
            creature = creatures[i]

            # Decrease energy by 1 every single frame
            creature.energy -= 1

            # If energy is depleted naturally, mark as dead and remove
            if creature.energy <= 0:
                creature.alive = False
                creatures.pop(i)
                nets.pop(i)
                ge.pop(i)
                continue

            # 1. Calculate raw distances to Food, Poison, and Wolf
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
            dist_top = min(creature.y, 200)
            dist_bottom = min(600 - creature.y, 200)
            dist_left = min(creature.x, 200)
            dist_right = min(800 - creature.x, 200)

            # 3. Pass sensory inputs into neural network (safely matches network input count)
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
            expected_in = len(nets[i].input_nodes)
            output = nets[i].activate(all_inputs[:expected_in])

            # 3. Highest output value maps to direction (0: Up, 1: Down, 2: Left, 3: Right)
            # Break ties randomly so untrained Gen 0 networks flicker and explore instead of locking into one wall
            max_val = max(output)
            best_indices = [idx for idx, val in enumerate(output) if abs(val - max_val) < 1e-5]
            decision = random.choice(best_indices) if len(best_indices) > 1 else best_indices[0]
            creature.move(decision)

            # 4. Out-of-bounds / wall collision: catastrophic penalty (-50 fitness)
            if (
                creature.rect.left < 0
                or creature.rect.right > SIM_WIDTH
                or creature.rect.top < 0
                or creature.rect.bottom > SIM_HEIGHT
            ):
                ge[i].fitness -= 50
                creature.alive = False
                creatures.pop(i)
                nets.pop(i)
                ge.pop(i)
                continue

            # 5. Reward +0.1 fitness per frame alive
            ge[i].fitness += 0.1

            # 6. Food collision: +20 fitness and respawn food
            if creature.rect.colliderect(food.rect):
                ge[i].fitness += 20
                food.respawn()

            # 7. Poison collision: instant kill, fitness penalty, and immediate array removal
            if creature.rect.colliderect(poison.rect):
                ge[i].fitness -= 20
                creature.alive = False
                poison.respawn()
                creatures.pop(i)
                nets.pop(i)
                ge.pop(i)
                continue

            # 8. Wolf collision: instant kill, -30 fitness penalty, and immediate array removal
            if creature.rect.colliderect(wolf.rect):
                ge[i].fitness -= 30
                creature.alive = False
                creatures.pop(i)
                nets.pop(i)
                ge.pop(i)
                continue

        # When all creatures have died, break loop to advance to next generation
        if len(creatures) == 0:
            break

        # Identify alpha creature with the highest current fitness score
        alpha_genome = None
        alpha_creature = None
        if ge:
            max_idx = max(range(len(ge)), key=lambda idx: ge[idx].fitness)
            alpha_genome = ge[max_idx]
            alpha_net = nets[max_idx]
            alpha_creature = creatures[max_idx]

            global best_genome_overall
            if best_genome_overall is None or alpha_genome.fitness > best_genome_overall.fitness:
                best_genome_overall = alpha_genome

        # Visual rendering occurs only when RENDER_MODE is True
        if RENDER_MODE:
            # Rendering
            screen.fill(WHITE)

            # Simulation field (left 800x600)
            food.draw(screen)
            poison.draw(screen)
            wolf.draw(screen)

            # Draw blue stamina bar hovering slightly above the Wolf
            stamina_bar_width = max(0, int((wolf.stamina / wolf.max_stamina) * wolf.rect.width))
            wolf_bar_x = wolf.rect.x
            wolf_bar_y = max(0, wolf.rect.y - 6)
            wolf_bar_height = 3

            # Background track
            pygame.draw.rect(screen, (180, 180, 180), (wolf_bar_x, wolf_bar_y, wolf.rect.width, wolf_bar_height))
            # Blue stamina fill
            if stamina_bar_width > 0:
                pygame.draw.rect(screen, BLUE, (wolf_bar_x, wolf_bar_y, stamina_bar_width, wolf_bar_height))
            for creature in creatures:
                creature.draw(screen)

                # Draw green/red health bar hovering just above the creature's square
                bar_color = FOOD_GREEN if creature.energy >= 50 else RED
                bar_width = max(0, int((creature.energy / creature.max_energy) * creature.rect.width))
                bar_height = 3
                bar_x = creature.rect.x
                bar_y = max(0, creature.rect.y - 6)

                # Tiny background track
                pygame.draw.rect(screen, (180, 180, 180), (bar_x, bar_y, creature.rect.width, bar_height))
                # Dynamic energy fill
                if bar_width > 0:
                    pygame.draw.rect(screen, bar_color, (bar_x, bar_y, bar_width, bar_height))

            if alpha_creature is not None:
                # Sensory tracking debug lines for Alpha creature (faint, semi-transparent)
                line_overlay = pygame.Surface((SIM_WIDTH, SIM_HEIGHT), pygame.SRCALPHA)
                alpha_pos = alpha_creature.rect.center

                # Draw 200px Fog of War sight radius ring around Alpha creature
                pygame.draw.circle(line_overlay, (200, 200, 200, 50), alpha_pos, int(SIGHT_RADIUS), width=1)

                # Draw sensory rays only when target is within 200px sight radius
                if math.hypot(food.rect.centerx - alpha_pos[0], food.rect.centery - alpha_pos[1]) <= SIGHT_RADIUS:
                    pygame.draw.aaline(line_overlay, (46, 204, 113, 160), alpha_pos, food.rect.center)
                if math.hypot(poison.rect.centerx - alpha_pos[0], poison.rect.centery - alpha_pos[1]) <= SIGHT_RADIUS:
                    pygame.draw.aaline(line_overlay, (155, 89, 182, 160), alpha_pos, poison.rect.center)
                if math.hypot(wolf.rect.centerx - alpha_pos[0], wolf.rect.centery - alpha_pos[1]) <= SIGHT_RADIUS:
                    pygame.draw.aaline(line_overlay, (231, 76, 60, 160), alpha_pos, wolf.rect.center)
                screen.blit(line_overlay, (0, 0))

                # Draw yellow highlight ring around alpha_creature
                pygame.draw.circle(screen, YELLOW, alpha_creature.rect.center, radius=18, width=2)

            # UI panel (right 400x600)
            pygame.draw.rect(screen, DARK_GRAY, (SIM_WIDTH, 0, UI_PANEL_WIDTH, WINDOW_HEIGHT))

            # Render neural network of alpha creature on the UI panel
            if alpha_genome is not None:
                draw_network(screen, alpha_genome, start_x=SIM_WIDTH, start_y=0)

            # Display "Time Left" countdown on UI panel
            time_left = max(0, 1000 - frame_counter)
            time_text = font.render(f"Time Left: {time_left}", True, YELLOW)
            screen.blit(time_text, (SIM_WIDTH + (UI_PANEL_WIDTH - time_text.get_width()) // 2, 55))

            pygame.display.flip()

        if RENDER_MODE:
            clock.tick(60)


def run_neat(config_path):
    """Loads configuration and runs the NEAT evolutionary simulation."""
    os.makedirs("checkpoints", exist_ok=True)
    # Load configuration
    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        config_path,
    )

    p = None
    checkpoint_file = None

    # 1. Check CLI arguments (e.g. `python main.py 100` or `python main.py checkpoints/neat-checkpoint-100`)
    for arg in sys.argv[1:]:
        arg_clean = arg.strip()
        if os.path.exists(arg_clean):
            checkpoint_file = arg_clean
            break
        candidate = f"checkpoints/neat-checkpoint-{arg_clean}"
        if os.path.exists(candidate):
            checkpoint_file = candidate
            break

    # 2. If not provided via CLI, prompt interactively if checkpoints exist
    if checkpoint_file is None:
        available_cps = []
        if os.path.exists("checkpoints"):
            available_cps = sorted(
                [f for f in os.listdir("checkpoints") if f.startswith("neat-checkpoint-")],
                key=lambda f: int(f.replace("neat-checkpoint-", "")) if f.replace("neat-checkpoint-", "").isdigit() else 0,
            )

        if available_cps and sys.stdin.isatty():
            latest_gen = available_cps[-1].replace("neat-checkpoint-", "")
            print(f"\n[Checkpoint Manager] Found {len(available_cps)} saved checkpoints.")
            print(f"Latest saved checkpoint is Generation {latest_gen}.")
            try:
                user_choice = input(
                    f"Enter generation number to resume (or press Enter for fresh start) [{latest_gen}]: "
                ).strip().lower()
                if user_choice:
                    target_file = (
                        user_choice
                        if user_choice.startswith("checkpoints/")
                        else f"checkpoints/neat-checkpoint-{user_choice}"
                    )
                    if os.path.exists(target_file):
                        checkpoint_file = target_file
                    else:
                        print(f"Checkpoint file '{target_file}' not found. Starting fresh population.")
            except (EOFError, KeyboardInterrupt):
                print("\nProceeding with fresh population.")

    # 3. Restore checkpoint if specified, otherwise initialize fresh population
    if checkpoint_file and os.path.exists(checkpoint_file):
        print(f"\n--> Resuming evolution from checkpoint: {checkpoint_file}")
        p = neat.Checkpointer.restore_checkpoint(checkpoint_file)
    else:
        print("\n--> Starting fresh population from scratch.")
        p = neat.Population(config)

    # Add StdOutReporter to display statistics in the terminal
    p.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    p.add_reporter(stats)

    # Automatically save simulation checkpoints every 10 generations in dedicated directory
    p.add_reporter(neat.Checkpointer(generation_interval=10, filename_prefix='checkpoints/neat-checkpoint-'))

    # Run simulation for up to 500 generations
    winner = None
    try:
        winner = p.run(eval_genomes, 500)
    except KeyboardInterrupt:
        print("\n[Ctrl+C detected] Simulation manually interrupted by user.")
        winner = p.best_genome or best_genome_overall

    # Save the ultimate winning genome permanently to best_dna.pkl
    target_genome = winner or p.best_genome or best_genome_overall
    if target_genome is not None:
        print(f"\nBest genome:\n{target_genome}")
        save_path = os.path.join(os.path.dirname(os.path.abspath(config_path)), "best_dna.pkl")
        with open(save_path, "wb") as file:
            pickle.dump(target_genome, file)
        print(f"Saved best genome permanently to {save_path}")
    else:
        print("Simulation stopped before any genome could be evaluated.")


# Alias run to run_neat
run = run_neat


if __name__ == "__main__":
    local_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(local_dir, "config.txt")
    run(config_path)
