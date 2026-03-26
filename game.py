import json
import os
import sys
import textwrap

class GameState:
    """Przechowuje stan gry: ekwipunek i zmienne flagi."""
    def __init__(self):
        self.inventory = [] 
        self.flags = {}     

    def add_item(self, item):
        if item not in self.inventory:
            self.inventory.append(item)
            return f"--- [ZDOBYTO PRZEDMIOT: {item}] ---"
        return ""

    def remove_item(self, item):
        if item in self.inventory:
            self.inventory.remove(item)
            return f"--- [UTRACONO PRZEDMIOT: {item}] ---"
        return ""

    def set_flag(self, key, value):
        self.flags[key] = value

    def check_requirement(self, req_type, req_value):
        if req_type == "has_item":
            return req_value in self.inventory
        elif req_type == "not_has_item":
            return req_value not in self.inventory
        elif req_type == "state_check":
            for k, v in req_value.items():
                if self.flags.get(k) != v:
                    return False
            return True
        elif req_type == "not_has_state":
             return not self.flags.get(req_value, False)
        return True

class GameEngine:
    def __init__(self, scenario_file):
        self.state = GameState()
        self.scenes = {}
        self.current_scene_id = None
        self.game_title = "Gra Tekstowa"
        
        # Ustawienia terminala (domyślne, nadpisywane przez JSON)
        self.terminal_width = 80
        self.terminal_height = 24
        
        self.valid_items = []
        self.valid_states = []
        
        self.load_scenario(scenario_file)

    def load_scenario(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.game_title = data.get('game_title', 'Gra')
                self.current_scene_id = data.get('start_node_id')
                self.terminal_width = data.get('terminal_width', 80)
                self.terminal_height = data.get('terminal_height', 24)
                
                self.valid_items = data.get('items', [])
                self.valid_states = data.get('states', [])
                
                for scene in data.get('scenes', []):
                    self.scenes[scene['id']] = scene
                    
                self.validate_scenario()
                
        except FileNotFoundError:
            print("Błąd: Nie znaleziono pliku scenariusza.")
            sys.exit(1)
        except json.JSONDecodeError:
            print("Błąd: Plik scenariusza ma niepoprawny format JSON.")
            sys.exit(1)

    def validate_scenario(self):
        """Sprawdza, czy w scenariuszu nie ma literówek w nazwach przedmiotów i stanów."""
        for scene in self.scenes.values():
            for opt in scene.get('options', []):
                reqs = opt.get('requirements', {})
                
                # Sprawdzanie literówek w wymaganiach
                if 'has_item' in reqs and reqs['has_item'] not in self.valid_items:
                    print(f"[OSTRZEŻENIE] Literówka? Przedmiot '{reqs['has_item']}' w scenie '{scene['id']}' nie istnieje na liście 'items'!")
                
                effects = opt.get('effects', {})
                # Sprawdzanie literówek w efektach
                if 'add_item' in effects:
                    items = effects['add_item'] if isinstance(effects['add_item'], list) else [effects['add_item']]
                    for item in items:
                        if item not in self.valid_items:
                            print(f"[OSTRZEŻENIE] Literówka? Przedmiot '{item}' dodawany w scenie '{scene['id']}' nie istnieje na liście 'items'!")

    def get_scene(self, scene_id):
        return self.scenes.get(scene_id)

    def print_wrapped(self, text):
        """Formatuje tekst tak, aby nie przekraczał szerokości terminala (zachowuje entery dla ASCII art)."""
        for line in text.split('\n'):
            if not line.strip():
                print()
            else:
                print(textwrap.fill(line, width=self.terminal_width))

    def clear_screen(self):
        """Czyści ekran konsoli w zależności od systemu operacyjnego."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def process_input(self, user_input, current_scene):
        user_words = user_input.lower().split()
        
        for option in current_scene.get('options', []):
            is_blocked = False
            for neg in option.get('negative_keywords', []):
                if neg in user_words:
                    is_blocked = True
                    break
            if is_blocked:
                continue

            is_match = False
            for key in option.get('keywords', []):
                if key in user_words:
                    is_match = True
                    break
            
            if is_match:
                reqs = option.get('requirements', {})
                reqs_met = True
                for req_type, req_value in reqs.items():
                    if not self.state.check_requirement(req_type, req_value):
                        reqs_met = False
                        break
                
                if reqs_met:
                    return option, "success"
                else:
                    if 'failure_text' in option:
                        return option, "failure"
                    continue

        return None, None

    def apply_effects(self, option):
        """Aplikuje efekty i zwraca połączony tekst komunikatów (np. o zdobyciu przedmiotu)."""
        effects = option.get('effects', {})
        messages = []
        
        # Obsługa wielu przedmiotów (lista) lub jednego (string)
        if 'add_item' in effects:
            items_to_add = effects['add_item']
            if not isinstance(items_to_add, list):
                items_to_add = [items_to_add]
                
            for item in items_to_add:
                msg = self.state.add_item(item)
                if msg: messages.append(msg)
            
        if 'remove_item' in effects:
            items_to_remove = effects['remove_item']
            if not isinstance(items_to_remove, list):
                items_to_remove = [items_to_remove]
                
            for item in items_to_remove:
                msg = self.state.remove_item(item)
                if msg: messages.append(msg)
            
        if 'set_state' in effects:
            for k, v in effects['set_state'].items():
                self.state.set_flag(k, v)
                
        return "\n".join(messages)

    def play(self):
        message = "" # Bufor na komunikaty zwrotne (wyświetlane po wyczyszczeniu ekranu)

        while True:
            self.clear_screen()
            scene = self.get_scene(self.current_scene_id)
            
            if not scene:
                print("Błąd: Nieznana scena. Koniec gry.")
                break

            # Nagłówek gry
            self.print_wrapped(f"=== {self.game_title} ===")
            self.print_wrapped("-" * self.terminal_width)
            
            # Tekst sceny (lub ASCII art)
            self.print_wrapped(scene['text'])
            self.print_wrapped("-" * self.terminal_width)
            
            # Wyświetlanie komunikatów z poprzedniej tury (np. "Zdobyto klucz")
            if message:
                self.print_wrapped(f"\n{message}")
                message = "" # Czyścimy bufor po wyświetleniu

            if not scene.get('options'):
                self.print_wrapped("\nKONIEC GRY.")
                break
            
            # Pobieranie komendy
            user_input = input("\n> ").strip()
            
            if user_input.lower() in ['q', 'wyjście', 'exit']:
                self.clear_screen()
                print("Do zobaczenia!")
                sys.exit(0)

            if not user_input:
                continue

            # Logika
            selected_option, status = self.process_input(user_input, scene)

            if selected_option:
                if status == "success":
                    # Zbieramy custom_text jeśli istnieje
                    if 'custom_text' in selected_option:
                        message = selected_option['custom_text']
                    
                    # Aplikujemy efekty i dopisujemy komunikaty o przedmiotach
                    effects_msg = self.apply_effects(selected_option)
                    if effects_msg:
                        message = message + "\n" + effects_msg if message else effects_msg
                    
                    # Zmiana sceny
                    target_id = selected_option.get('target_id', self.current_scene_id)
                    if target_id != self.current_scene_id:
                        self.current_scene_id = target_id
                        
                elif status == "failure":
                    message = selected_option.get('failure_text', 'Nie możesz tego teraz zrobić.')
            else:
                message = scene.get('fallback_text', 'Nie rozumiem co chcesz zrobić. Spróbuj inaczej.')

if __name__ == "__main__":
    game = GameEngine("scenariusz.json")
    game.play()
