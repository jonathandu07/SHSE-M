import os

filepath = r'c:\Users\alpha\Documents\GitHub\SHSE-M\frontend\main.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

content = "".join(lines)

# Fix fuel selection
old_fuel = """        # Mode carburant
        fuel_row = BoxLayout(size_hint_y=None, height=52, spacing=16)
        fuel_row.add_widget(Label(text="Mode carburant :", color=COLORS["GAXD"],
                                   font_size="14sp", size_hint_x=0.3))
        self._fuel_btns = {}
        self._selected_fuel = "multi_carburant"
        for fuel in ["multi_carburant"]:
            fb = ArchButton(fuel.upper(), font_size="14sp")
            fb.set_selected(True)
            fb.bind(on_press=lambda b, f=fuel: self._select_fuel(f))
            fuel_row.add_widget(fb)
            self._fuel_btns[fuel] = fb
        param_card.add_widget(fuel_row)
        page.add_widget(param_card)"""

new_fuel = """        # Mode carburant
        fuel_row = BoxLayout(size_hint_y=None, height=52, spacing=10)
        fuel_row.add_widget(Label(text="Source :", color=COLORS["GAXD"],
                                   font_size="14sp", size_hint_x=0.2))
        self._fuel_btns = {}
        self._selected_fuel = "multi"
        fuels = [("MULTI", "multi"), ("DIESEL", "diesel"), ("ESSENCE", "essence"), ("H2", "hydrogene")]
        for label, code in fuels:
            fb = ArchButton(label, font_size="12sp")
            fb.set_selected(code == self._selected_fuel)
            fb.bind(on_press=lambda b, f=code: self._select_fuel(f))
            fuel_row.add_widget(fb)
            self._fuel_btns[code] = fb
        param_card.add_widget(fuel_row)
        page.add_widget(param_card)"""

# Fix _read_float
old_read = """    def _read_float(self, key: str, default: float) -> float:
        try:
            return float((self._fields[key].text or "").replace(",", "."))
        except Exception:
            return default"""

new_read = """    def _read_float(self, key: str, default: Optional[float] = None) -> Optional[float]:
        try:
            txt = (self._fields[key].text or "").strip().replace(",", ".")
            if not txt:
                return default
            return float(txt)
        except Exception:
            return default"""

# Fix launch_generation
old_launch = """        arch = self._selected_arch
        ncyl_map = {"L4": 4, "L6": 6, "V8": 8, "V12": 12}
        ncyl = ncyl_map.get(arch, 6)
        alesage_mm = self._read_float("alesage_mm", 130.0)
        course_mm = self._read_float("course_mm", 150.0)"""

new_launch = """        arch = self._selected_arch
        ncyl_map = {"L4": 4, "L6": 6, "V8": 8, "V12": 12}
        ncyl = ncyl_map.get(arch, 6)
        alesage_mm = self._read_float("alesage_mm", None)
        course_mm = self._read_float("course_mm", None)"""

content = content.replace(old_fuel, new_fuel)
content = content.replace(old_read, new_read)
content = content.replace(old_launch, new_launch)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Frontend fix successful")
