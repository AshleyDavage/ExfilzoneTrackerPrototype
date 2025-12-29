import flet as ft
import json
import os
import sys

# --- Configuration & Data ---
def get_base_path():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
ITEMS_FILE = os.path.join(BASE_DIR, "./data/items.json")
TRACKED_ITEMS_FILE = os.path.join(BASE_DIR, "./data/tracked_items.json") 
APP_TITLE = "Exfilzone Tracker" # Changed Application Title

CATEGORY_COLORS = {
    "High Value": ft.Colors.AMBER_700, "Household": ft.Colors.LIGHT_BLUE_500,
    "Intel": ft.Colors.PURPLE_ACCENT_200, "Combustible": ft.Colors.DEEP_ORANGE_ACCENT_400,
    "Electric": ft.Colors.YELLOW_ACCENT_700, "Power": ft.Colors.LIGHT_GREEN_ACCENT_700,
    "Building": ft.Colors.BROWN_400, "Tools": ft.Colors.CYAN_600,
    "Medical Supplies": ft.Colors.GREEN_ACCENT_700,
    "N/A": ft.Colors.GREY_500
}
# Width for header action buttons/spacers to help with title centering
HEADER_SIDE_ELEMENT_WIDTH = 100 # Increased to better accommodate "Add New Item" button text
ICON_BUTTON_WIDTH_ESTIMATE = 56 
HEADER_ACTION_BUTTON_WIDTH = 140

def load_items_from_json():
    if not os.path.exists(ITEMS_FILE):
        print(f"CRITICAL ERROR: '{ITEMS_FILE}' not found. Please ensure it exists in the same directory as the application. App will start with no available items.")
        return []
    try:
        with open(ITEMS_FILE, "r", encoding='utf-8') as f: items = json.load(f)
        if not isinstance(items, list): print(f"ERROR: '{ITEMS_FILE}' not a list."); return []
        for item in items:
            if not (isinstance(item, dict) and "id" in item and "name" in item and "category" in item and "value" in item):
                print(f"ERROR: Invalid item structure: {item}.")
        return items
    except Exception as e: print(f"ERROR: Loading '{ITEMS_FILE}': {e}."); return []

class AppState:
    def __init__(self):
        self.available_items = load_items_from_json()
        self.wanted_items_data = []
        self.item_categories = ["All Categories", "High Value", "Household", "Intel", "Combustible", "Electric", "Power", "Building", "Tools", "Medical Supplies"]
        self.selected_category = "All Categories" 
        self.editing_wanted_item_entry = None
        self.item_sort_mode = "alphabetical"
        self.item_to_delete_on_page = None # For delete confirmation dialog on ItemsPage
        self._load_tracked_items()

    def _serialize_tracked_item(self, entry):
        try: quantity = int(entry["quantity_tf"].value)
        except: quantity = 1 
        return {"item_id": entry["item"]["id"], "quantity": quantity}

    def _save_tracked_items(self):
        data_to_save = [self._serialize_tracked_item(entry) for entry in self.wanted_items_data]
        try:
            with open(TRACKED_ITEMS_FILE, "w", encoding='utf-8') as f: json.dump(data_to_save, f, indent=4)
            print(f"DEBUG: Saved {len(data_to_save)} tracked items.")
        except IOError as e: print(f"ERROR: Could not save tracked items: {e}")

    def _load_tracked_items(self):
        if not os.path.exists(TRACKED_ITEMS_FILE): print(f"DEBUG: No tracked items file found."); return
        try:
            with open(TRACKED_ITEMS_FILE, "r", encoding='utf-8') as f: loaded_data = json.load(f)
            if not isinstance(loaded_data, list): self.wanted_items_data = []; self._save_tracked_items(); return
            temp_wanted_items = []
            for saved_entry in loaded_data:
                if not (isinstance(saved_entry, dict) and "item_id" in saved_entry and "quantity" in saved_entry): continue
                item_id, quantity = saved_entry["item_id"], saved_entry["quantity"]
                full_item_dict = next((item for item in self.available_items if item["id"] == item_id), None)
                if full_item_dict:
                    quantity_tf = ft.TextField(value=str(quantity), width=50, text_align=ft.TextAlign.CENTER, border=ft.InputBorder.NONE, read_only=True)
                    temp_wanted_items.append({"item": full_item_dict, "quantity_tf": quantity_tf})
                else: print(f"WARNING: Item ID '{item_id}' not in available items. Skipping.")
            self.wanted_items_data = temp_wanted_items
            print(f"DEBUG: Loaded {len(self.wanted_items_data)} tracked items.")
        except Exception as e: print(f"ERROR: Loading {TRACKED_ITEMS_FILE}: {e}."); self.wanted_items_data = []

# --- Page View Functions ---

def HomePageView(page: ft.Page, app_state: AppState):
    app_title_words = APP_TITLE.split(); wrapped_app_title = "\n".join(app_title_words)
    # Welcome message removed
    view = ft.View("/", [
        ft.Text(wrapped_app_title, size=26, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
        # ft.Text(wrapped_welcome_message, size=20, text_align=ft.TextAlign.CENTER), # Welcome message removed
        ft.Container(height=30), # Increased spacing a bit
        ft.ElevatedButton("View Items", icon=None, on_click=lambda _: page.go("/items"), width=250, height=50),
        ft.Container(height=10),
        ft.ElevatedButton("Tracked Item List", icon=None, on_click=lambda _: page.go("/wanted"), width=250, height=50)
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, vertical_alignment=ft.MainAxisAlignment.CENTER, spacing=20, padding=30)
    return view

def ItemsPageView(page: ft.Page, app_state: AppState):
    print("DEBUG: Building ItemsPageView (Icon Button for Add New Item).")

    ITEMS_AREA_WIDTH = 436 
    ITEM_MAX_EXTENT = 140
    ITEM_CHILD_ASPECT_RATIO = 1.2

    items_grid_view = ft.GridView(
        expand=True,
        max_extent=ITEM_MAX_EXTENT, 
        child_aspect_ratio=ITEM_CHILD_ASPECT_RATIO,
        spacing=8,
        run_spacing=10,
    )

    sort_button_ref = ft.Ref[ft.IconButton]()
    new_item_dialog_ref = ft.Ref[ft.AlertDialog]()
    new_item_name_input_ref = ft.Ref[ft.TextField]()
    new_item_value_input_ref = ft.Ref[ft.TextField]()
    new_item_category_dropdown_ref = ft.Ref[ft.Dropdown]()
    _new_item_dialog_instance = None 
    delete_confirm_dialog_ref = ft.Ref[ft.AlertDialog]()
    delete_confirm_dialog_text_ref = ft.Ref[ft.Text]()

    def show_snackbar(message: str, is_error: bool = False):
        # (This function remains the same)
        sb_content = ft.Text(message, color=ft.Colors.ERROR if is_error else None)
        page.overlay.append(ft.SnackBar(content=sb_content, open=True)); page.update()

    def parse_item_value(value_str: str) -> float:
        # (This function remains the same)
        if isinstance(value_str, (int, float)): return float(value_str)
        if isinstance(value_str, str):
            try: return float(value_str.replace("$", "").replace(",", ""))
            except ValueError: return 0.0
        return 0.0

    def format_value_for_storage(value_input_str: str) -> str | None:
        # (This function remains the same)
        try:
            cleaned_str = value_input_str.replace("$", "").replace(",", "").strip()
            if not cleaned_str: return None
            val = float(cleaned_str);
            if val < 0: return None
            return f"{int(round(val)):,}"
        except ValueError: return None

    def generate_new_item_id_from_count(): return f"item_{len(app_state.available_items)}"

    def confirm_delete_item(e):
        # (This function remains the same)
        if app_state.item_to_delete_on_page:
            item_to_remove = app_state.item_to_delete_on_page
            app_state.available_items = [item for item in app_state.available_items if item["id"] != item_to_remove["id"]]
            try:
                with open(ITEMS_FILE, "w", encoding='utf-8') as f: json.dump(app_state.available_items, f, indent=4)
                show_snackbar(f"Item '{item_to_remove['name']}' deleted.")
                found_in_tracked = False
                for entry in list(app_state.wanted_items_data): 
                    if entry["item"]["id"] == item_to_remove["id"]:
                        app_state.wanted_items_data.remove(entry); found_in_tracked = True
                if found_in_tracked: app_state._save_tracked_items()
            except IOError as io_err:
                print(f"ERROR: Could not update {ITEMS_FILE} after delete: {io_err}"); show_snackbar(f"Error deleting item.", is_error=True)
            app_state.item_to_delete_on_page = None
            rebuild_filtered_items_display(); page.update()
        if delete_confirm_dialog_ref.current: page.close(delete_confirm_dialog_ref.current)

    def open_delete_confirm_dialog(item_to_delete):
        # (This function remains the same)
        app_state.item_to_delete_on_page = item_to_delete
        dialog_text = f"Are you sure you want to delete '{item_to_delete['name']}'? This cannot be undone."
        if not delete_confirm_dialog_ref.current:
             delete_confirm_dialog_ref.current = ft.AlertDialog(modal=True, title=ft.Text("Confirm Deletion"), content=ft.Text(ref=delete_confirm_dialog_text_ref), actions=[ft.TextButton("Cancel", on_click=lambda e: page.close(delete_confirm_dialog_ref.current)), ft.ElevatedButton("Delete", on_click=confirm_delete_item, color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_ACCENT_700)], actions_alignment=ft.MainAxisAlignment.SPACE_EVENLY)
        if delete_confirm_dialog_text_ref.current: delete_confirm_dialog_text_ref.current.value = dialog_text; 
        if delete_confirm_dialog_text_ref.current and delete_confirm_dialog_text_ref.current.page: delete_confirm_dialog_text_ref.current.update()
        page.open(delete_confirm_dialog_ref.current)

    def rebuild_filtered_items_display():
        # (This function remains the same as the version where the spacer was removed from item_box_content)
        items_grid_view.controls.clear(); source_items_list = []
        if app_state.selected_category == "All Categories": source_items_list = list(app_state.available_items)
        else: source_items_list = [item for item in app_state.available_items if item.get("category") == app_state.selected_category]
        if source_items_list:
            if app_state.item_sort_mode == "value": source_items_list.sort(key=lambda x: parse_item_value(x.get("value", "0")), reverse=True)
            else: source_items_list.sort(key=lambda x: x.get("name", "").lower())
        if not source_items_list: print(f"No items in category: {app_state.selected_category}.")
        else:
            for item_dict in source_items_list:
                category_name = item_dict.get('category', 'N/A'); category_color = CATEGORY_COLORS.get(category_name, ft.Colors.GREY_500)
                item_name_text = ft.Text(value=item_dict.get("name", "Unnamed Item"), size=13, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER, tooltip=item_dict.get("name", "Unnamed Item"))
                item_category_text = ft.Text(category_name, size=11, color=category_color, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
                item_value_str = item_dict.get('value', 'N/A'); display_value = f"${item_value_str}" if item_value_str and item_value_str != 'N/A' else "No Value"
                item_value_text = ft.Text(display_value, size=11, weight=ft.FontWeight.NORMAL, color=ft.Colors.GREEN_700, text_align=ft.TextAlign.CENTER)
                delete_item_button = ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, icon_color=ft.Colors.RED_ACCENT_700, tooltip="Delete Item from Master List", icon_size=20, on_click=lambda e, item=item_dict: open_delete_confirm_dialog(item))
                value_and_delete_section = ft.Column([item_value_text, ft.Row([delete_item_button], alignment=ft.MainAxisAlignment.CENTER)], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                item_box_content = ft.Column([item_name_text, ft.Divider(height=1, thickness=0.5), item_category_text, value_and_delete_section], spacing=3, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                item_container = ft.Container(content=item_box_content, padding=8, border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT), border_radius=ft.border_radius.all(6))
                items_grid_view.controls.append(item_container)
        if items_grid_view.page: items_grid_view.update()

    def category_changed_handler(e): 
        # (This function remains the same)
        app_state.selected_category = e.control.value; rebuild_filtered_items_display(); page.update() 
    
    def toggle_sort_mode(e):
        # (This function remains the same)
        if app_state.item_sort_mode == "alphabetical": app_state.item_sort_mode = "value"; 
        else: app_state.item_sort_mode = "alphabetical"
        if sort_button_ref.current: 
            sort_button_ref.current.icon = ft.Icons.SORT_BY_ALPHA_ROUNDED if app_state.item_sort_mode == "alphabetical" else ft.Icons.SORT_ROUNDED
            sort_button_ref.current.tooltip = "Sort by Name" if app_state.item_sort_mode == "alphabetical" else "Sort by Value (High to Low)"
            sort_button_ref.current.update()
        rebuild_filtered_items_display(); page.update()

    def confirm_add_new_item_to_master_list(e):
        # (This function remains the same)
        nonlocal _new_item_dialog_instance
        name = new_item_name_input_ref.current.value.strip(); value_str_input = new_item_value_input_ref.current.value; category = new_item_category_dropdown_ref.current.value
        if not name: show_snackbar("Item name cannot be empty.", is_error=True); return
        if not category: show_snackbar("Please select a category.", is_error=True); return
        formatted_value = format_value_for_storage(value_str_input)
        if formatted_value is None: show_snackbar("Invalid value (e.g., 1500 or $1,500).", is_error=True); return
        new_id = generate_new_item_id_from_count()
        new_item = {"id": new_id, "name": name, "value": formatted_value, "category": category}
        app_state.available_items.append(new_item); app_state.available_items.sort(key=lambda x: x.get("name", "").lower()) 
        try:
            with open(ITEMS_FILE, "w", encoding='utf-8') as f: json.dump(app_state.available_items, f, indent=4)
            show_snackbar(f"Item '{name}' added successfully!")
        except IOError as io_err: print(f"ERROR: Could not write to {ITEMS_FILE}: {io_err}"); show_snackbar("Error: Could not save item.", is_error=True); return 
        rebuild_filtered_items_display(); page.update()
        if _new_item_dialog_instance: page.close(_new_item_dialog_instance)

    def open_add_new_item_dialog(e):
        # (This function remains the same, dialog definition is below)
        nonlocal _new_item_dialog_instance
        if not _new_item_dialog_instance: 
            new_item_category_options = [ft.dropdown.Option(cat) for cat in app_state.item_categories if cat != "All Categories"]
            _new_item_dialog_instance = ft.AlertDialog(ref=new_item_dialog_ref, modal=True, title=ft.Text("Add New Item"), content=ft.Column([ft.TextField(ref=new_item_name_input_ref, label="Item Name", autofocus=True), ft.TextField(ref=new_item_value_input_ref, label="Item Value", hint_text="e.g., 1500 or $1,500", keyboard_type=ft.KeyboardType.TEXT), ft.Dropdown(ref=new_item_category_dropdown_ref, label="Category", options=new_item_category_options, hint_text="Select a category")], tight=True, spacing=15, width=300), actions=[ft.TextButton("Cancel", on_click=lambda ev: page.close(_new_item_dialog_instance) if _new_item_dialog_instance else None), ft.ElevatedButton("Confirm Add", on_click=confirm_add_new_item_to_master_list)], actions_alignment=ft.MainAxisAlignment.SPACE_EVENLY)
        if new_item_name_input_ref.current: new_item_name_input_ref.current.value = ""
        if new_item_value_input_ref.current: new_item_value_input_ref.current.value = ""
        if new_item_category_dropdown_ref.current: new_item_category_dropdown_ref.current.value = None 
        page.open(_new_item_dialog_instance)

    sort_button = ft.IconButton(ref=sort_button_ref, icon=ft.Icons.SORT_BY_ALPHA_ROUNDED if app_state.item_sort_mode == "alphabetical" else ft.Icons.SORT_ROUNDED, tooltip="Sort by Name" if app_state.item_sort_mode == "alphabetical" else "Sort by Value (High to Low)", on_click=toggle_sort_mode, icon_size=20)
    category_filter_dropdown = ft.Dropdown(hint_text="Select Category", options=[ft.dropdown.Option(cat) for cat in app_state.item_categories], value=app_state.selected_category, on_change=category_changed_handler, expand=True)
    filter_row_content = ft.Row([sort_button, category_filter_dropdown], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
    
    rebuild_filtered_items_display() 

    # --- Updated Header: "Add New Item" is now an IconButton ---
    add_new_item_icon_button = ft.IconButton(
        icon=ft.Icons.ADD_ROUNDED, # Using a simple '+' icon
        icon_color=ft.Colors.GREEN_ACCENT_700,
        tooltip="Add New Item",
        on_click=open_add_new_item_dialog,
        icon_size=24, # Adjust size as needed
        width=ICON_BUTTON_WIDTH_ESTIMATE # Ensure it takes up defined space for balance
    )
    
    header_row = ft.Row(
        [
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT_ROUNDED, on_click=lambda _: page.go("/"), tooltip="Back to Home", width=ICON_BUTTON_WIDTH_ESTIMATE), 
            ft.Text("Items", size=24, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER, expand=True), 
            add_new_item_icon_button # Using the new IconButton
        ], 
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN # This will space out the 3 elements
    )
    
    view_controls = [
        header_row, 
        ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT, thickness=0.5), 
        ft.Container(filter_row_content, width=ITEMS_AREA_WIDTH, padding=ft.padding.symmetric(vertical=10), alignment=ft.alignment.center), 
        ft.Container(content=items_grid_view, width=ITEMS_AREA_WIDTH, expand=True, alignment=ft.alignment.top_center)
        # The ElevatedButton for "Add New Item" at the bottom is removed as it's now in the header.
    ]
    
    view = ft.View("/items", controls=view_controls, padding=ft.padding.only(left=10, right=10, top=20, bottom=20), horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    return view

def WantedPageView(page: ft.Page, app_state: AppState):
    wanted_items_display_column = ft.Column(spacing=0, scroll=ft.ScrollMode.ADAPTIVE)
    add_item_dialog_ref = ft.Ref[ft.AlertDialog]()
    # Changed dialog category selection back to standard Dropdown
    dialog_category_dropdown_ref = ft.Ref[ft.Dropdown]() 
    # Changed dialog item selection back to standard Dropdown
    dialog_item_dropdown_ref = ft.Ref[ft.Dropdown]() # Was dialog_item_list_view_ref
    quantity_input_ref = ft.Ref[ft.TextField]()
    actual_dialog_control = None 
    _dialog_current_category = "All Categories"
    # _dialog_selected_item_obj is no longer needed as dropdown value (ID) will be used.

    def show_snackbar(message: str, is_error: bool = False):
        sb_content = ft.Text(message, color=ft.Colors.ERROR if is_error else None)
        page.overlay.append(ft.SnackBar(content=sb_content, open=True)); page.update()

    def reset_dialog_to_add_mode():
        nonlocal actual_dialog_control, _dialog_current_category
        _dialog_current_category = "All Categories"
        if actual_dialog_control: 
            actual_dialog_control.title.value = "New Item"
            if actual_dialog_control.actions and len(actual_dialog_control.actions) > 1 and isinstance(actual_dialog_control.actions[-1], ft.ElevatedButton):
                actual_dialog_control.actions[-1].text = "Add to List"
        if dialog_category_dropdown_ref.current: dialog_category_dropdown_ref.current.value = "All Categories"
        update_dialog_item_dropdown_options("All Categories") # Populate items for "All"
        if dialog_item_dropdown_ref.current: dialog_item_dropdown_ref.current.value = None # Clear selected item
        if quantity_input_ref.current: quantity_input_ref.current.value = "1"
        app_state.editing_wanted_item_entry = None

    def update_dialog_item_dropdown_options(selected_category_in_dialog: str):
        # This now populates the item_dropdown_ref
        if not dialog_item_dropdown_ref.current: return
        new_item_options = []; items_to_filter = app_state.available_items
        filtered_items = []
        if selected_category_in_dialog == "All Categories": filtered_items = list(items_to_filter)
        else: filtered_items = [item for item in items_to_filter if item.get("category") == selected_category_in_dialog]
        filtered_items.sort(key=lambda item_dict: item_dict.get("name", "").lower())
        
        for item_dict in filtered_items:
            new_item_options.append(ft.dropdown.Option(key=item_dict["id"], text=item_dict.get("name", "Unnamed")))
        
        dialog_item_dropdown_ref.current.options = new_item_options
        dialog_item_dropdown_ref.current.value = None 
        if dialog_item_dropdown_ref.current.page: dialog_item_dropdown_ref.current.update()

    def dialog_category_changed_handler(e): # For standard dropdown in dialog
        nonlocal _dialog_current_category
        _dialog_current_category = e.control.value
        update_dialog_item_dropdown_options(_dialog_current_category)
        
    def remove_wanted_item(item_entry_to_remove):
        if item_entry_to_remove in app_state.wanted_items_data:
            app_state.wanted_items_data.remove(item_entry_to_remove); app_state._save_tracked_items(); rebuild_wanted_list_display(); page.update()

    def open_item_dialog_for_edit(entry_to_edit):
        nonlocal actual_dialog_control, _dialog_current_category
        app_state.editing_wanted_item_entry = entry_to_edit
        _dialog_current_category = entry_to_edit["item"].get("category", "All Categories")
        
        if dialog_category_dropdown_ref.current: dialog_category_dropdown_ref.current.value = _dialog_current_category
        update_dialog_item_dropdown_options(_dialog_current_category) # Populate items for this category
        
        if dialog_item_dropdown_ref.current: dialog_item_dropdown_ref.current.value = entry_to_edit["item"]["id"] # Pre-select item
        if quantity_input_ref.current: quantity_input_ref.current.value = entry_to_edit["quantity_tf"].value
        
        if actual_dialog_control:
            actual_dialog_control.title.value = "Edit Item" 
            if actual_dialog_control.actions and len(actual_dialog_control.actions) > 1 and isinstance(actual_dialog_control.actions[-1], ft.ElevatedButton):
                actual_dialog_control.actions[-1].text = "Save Changes"
        page.open(actual_dialog_control)

    def rebuild_wanted_list_display():
        wanted_items_display_column.controls.clear()
        for index, entry in enumerate(app_state.wanted_items_data):
            item_name = entry["item"]["name"]; quantity_tf_control = entry["quantity_tf"]
            edit_button = ft.IconButton(icon=ft.Icons.EDIT_ROUNDED, tooltip="Edit item", icon_size=20, on_click=lambda _, ce=entry: open_item_dialog_for_edit(ce))
            remove_button = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE_ROUNDED, tooltip="Remove item", icon_color=ft.Colors.ERROR, icon_size=20, on_click=lambda _, ce=entry: remove_wanted_item(ce))
            item_container = ft.Container(ft.Row([ft.Text(item_name, expand=True), quantity_tf_control, edit_button, remove_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=ft.padding.symmetric(vertical=10, horizontal=5))
            wanted_items_display_column.controls.append(item_container)
            if index < len(app_state.wanted_items_data) - 1: wanted_items_display_column.controls.append(ft.Divider(height=1, thickness=0.5, color=ft.Colors.OUTLINE_VARIANT))
        if wanted_items_display_column.page: wanted_items_display_column.update()

    def change_dialog_quantity(delta: int):
        if quantity_input_ref.current:
            try:
                current_val = int(quantity_input_ref.current.value); new_val = current_val + delta
                if new_val >= 1: quantity_input_ref.current.value = str(new_val)
                if add_item_dialog_ref.current and add_item_dialog_ref.current.open: quantity_input_ref.current.update()
            except ValueError: quantity_input_ref.current.value = "1"
            if add_item_dialog_ref.current and add_item_dialog_ref.current.open: quantity_input_ref.current.update()

    def close_dialog_and_reset(e=None): 
        nonlocal actual_dialog_control
        if actual_dialog_control and hasattr(actual_dialog_control, 'open') and actual_dialog_control.open : page.close(actual_dialog_control)
        reset_dialog_to_add_mode()

    def confirm_add_item_from_dialog(e):
        nonlocal actual_dialog_control
        selected_item_id = dialog_item_dropdown_ref.current.value # Get ID from standard dropdown
        if not selected_item_id: show_snackbar("⚠️ Please select an item.", is_error=True); return
        if not quantity_input_ref.current: show_snackbar("Error: Quantity input not ready.", is_error=True); return
        quantity_str = quantity_input_ref.current.value
        try:
            quantity = int(quantity_str)
            if quantity <= 0: show_snackbar("Quantity must be > 0.", is_error=True); return
        except ValueError: show_snackbar("Invalid quantity.", is_error=True); return
        
        selected_item_dict = next((item for item in app_state.available_items if item["id"] == selected_item_id), None)
        if not selected_item_dict: show_snackbar("Error: Selected item data not found from ID.", is_error=True); return

        if app_state.editing_wanted_item_entry: 
            app_state.editing_wanted_item_entry["item"] = selected_item_dict 
            app_state.editing_wanted_item_entry["quantity_tf"].value = str(quantity) 
        else: 
            new_quantity_tf_for_list = ft.TextField(value=str(quantity), width=50, text_align=ft.TextAlign.CENTER, border=ft.InputBorder.NONE, read_only=True)
            app_state.wanted_items_data.append({"item": selected_item_dict, "quantity_tf": new_quantity_tf_for_list})
        app_state._save_tracked_items(); rebuild_wanted_list_display()
        if actual_dialog_control: page.close(actual_dialog_control)
        reset_dialog_to_add_mode(); page.update()
    
    dialog_category_options_for_standard_dropdown = [ft.dropdown.Option(cat) for cat in app_state.item_categories]
    quantity_row_in_dialog = ft.Row([ft.IconButton(icon=ft.Icons.REMOVE_ROUNDED, on_click=lambda e: change_dialog_quantity(-1)), ft.TextField(ref=quantity_input_ref, value="1", width=60, text_align=ft.TextAlign.CENTER, keyboard_type=ft.KeyboardType.NUMBER), ft.IconButton(icon=ft.Icons.ADD_ROUNDED, on_click=lambda e: change_dialog_quantity(1))], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER)
    
    actual_dialog_control = ft.AlertDialog(
        ref=add_item_dialog_ref, modal=True, title=ft.Text("New Item"),
        content=ft.Column(
            [
                ft.Dropdown( # Standard Dropdown for Category in Dialog
                    ref=dialog_category_dropdown_ref,
                    label="Category",
                    hint_text="Select a category",
                    options=dialog_category_options_for_standard_dropdown,
                    value="All Categories",
                    on_change=dialog_category_changed_handler,
                    expand=True,
                    autofocus=True
                ),
                ft.Dropdown( # Standard Dropdown for Item in Dialog
                    ref=dialog_item_dropdown_ref,
                    label="Item",
                    hint_text="Select an item",
                    options=[], # Populated by update_dialog_item_dropdown_options
                    expand=True
                ),
                quantity_row_in_dialog,
            ], tight=False, spacing=15, scroll=ft.ScrollMode.ADAPTIVE, width=300, # Adjusted width
               horizontal_alignment=ft.CrossAxisAlignment.STRETCH
        ), 
        actions=[ft.TextButton("Cancel", on_click=close_dialog_and_reset, expand=True), ft.ElevatedButton("Add to List", icon=None, on_click=confirm_add_item_from_dialog, expand=True)], 
        actions_alignment=ft.MainAxisAlignment.CENTER
    )

    def open_add_item_dialog_for_new(e): 
        nonlocal actual_dialog_control; reset_dialog_to_add_mode()         
        page.open(actual_dialog_control)
    
    def clear_all_tracked_items(e):
        app_state.wanted_items_data.clear(); app_state._save_tracked_items()
        rebuild_wanted_list_display(); page.update()
        show_snackbar("Tracked list cleared!")

    add_button = ft.ElevatedButton("Add Tracked Item", icon=None, on_click=open_add_item_dialog_for_new, height=50, width=220)
    rebuild_wanted_list_display() 
    header_row = ft.Row([ft.IconButton(icon=ft.Icons.CHEVRON_LEFT_ROUNDED, on_click=lambda _: page.go("/"), tooltip="Back to Home", width=ICON_BUTTON_WIDTH_ESTIMATE), ft.Text("Items to Collect", size=24, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER, expand=True), ft.IconButton(icon=ft.Icons.DELETE_SWEEP_ROUNDED, tooltip="Clear All Items", on_click=clear_all_tracked_items, width=ICON_BUTTON_WIDTH_ESTIMATE, icon_color=ft.Colors.ERROR)], vertical_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    view_controls = [header_row, ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT, thickness=0.5), ft.Container(content=wanted_items_display_column, width=320, expand=True, alignment=ft.alignment.top_center), ft.Container(content=ft.Row([add_button], alignment=ft.MainAxisAlignment.CENTER), padding=ft.padding.only(top=10))]
    view = ft.View("/wanted", controls=view_controls, padding=20, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    return view

def main(page: ft.Page):
    page.title = APP_TITLE # Updated title
    # --- Set window size ---
    page.window.width = 425
    page.window.height = 700
    # page.update() # May not be needed for initial size, but harmless
    
    page.theme_mode = ft.ThemeMode.SYSTEM 
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH 

    app_state = AppState()

    def route_change(route_event: ft.RouteChangeEvent):
        page.views.clear(); route = route_event.route
        if route == "/": page.views.append(HomePageView(page, app_state))
        elif route == "/items": page.views.append(ItemsPageView(page, app_state))
        elif route == "/wanted": page.views.append(WantedPageView(page, app_state))
        page.update()

    def view_pop(view_event: ft.ViewPopEvent):
        page.views.pop()
        if not page.views: page.go("/")
        page.update()

    page.on_route_change = route_change; page.on_view_pop = view_pop
    if not page.route or page.route == "": page.go("/")
    else: page.go(page.route)

# items.json is expected to exist in the same directory as the application.
# If it's missing on first run, load_items_from_json will print an error,
# and the app will start with no available items.

ft.app(target=main, view=ft.AppView.FLET_APP)