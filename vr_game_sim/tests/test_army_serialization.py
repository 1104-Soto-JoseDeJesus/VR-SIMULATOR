from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.main import (
    get_setup_data_for_saving,
    save_army_to_file,
    load_army_from_file,
)


def test_save_and_load_army(tmp_path):
    army = Army('A', Unit('pikemen', 5, initial_count=10))
    cfg = get_setup_data_for_saving([army])[0]
    file_path = tmp_path / 'army.json'
    save_army_to_file(cfg, file_path)
    loaded = load_army_from_file(file_path)
    assert loaded == cfg
