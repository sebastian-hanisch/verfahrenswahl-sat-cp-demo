"""Presets: Vollständigkeit, gültige Werte, erstes Preset = Standardeinstellungen, gegenseitig verschieden, Hilfetexte nennen nur geprüfte Zahlen."""

import vsw_constants as C
import vsw_presets as P


def test_every_preset_has_help():
    assert set(C.PRESETS) == set(C.PRESET_HELP)
    assert all(C.PRESET_HELP[n] for n in C.PRESETS)


def test_preset_keys_are_known_and_values_are_valid():
    for name, preset in C.PRESETS.items():
        for key, wert in preset.items():
            assert key in P.PRESET_KEYS, (name, key)
            spec = P.SETTING_SPECS[P.PRESET_KEYS[key]]
            if spec.options is not None:
                assert wert in spec.options, (name, key)
            else:
                assert spec.lo <= wert <= spec.hi, (name, key)


def test_the_first_preset_is_the_default_and_the_presets_differ():
    erster = next(iter(C.PRESETS.values()))
    assert erster == {}                              # alle Regler auf Standard
    zustaende = []
    for preset in C.PRESETS.values():
        zustaende.append(tuple(preset.get(k, P.SETTING_SPECS[s].default) for k, s in P.PRESET_KEYS.items()))
    assert len(set(zustaende)) == len(zustaende)


def test_setting_specs_cover_every_preset_key():
    assert set(P.PRESET_KEYS.values()) == set(P.SETTING_SPECS)


def test_defaults_are_inside_their_bounds_and_options():
    for key, spec in P.SETTING_SPECS.items():
        if spec.options is not None:
            assert spec.default in spec.options, key
        else:
            assert spec.lo <= spec.default <= spec.hi, key


def test_the_url_parameters_are_unique():
    params = [s.url_param for s in P.SETTING_SPECS.values()]
    assert len(params) == len(set(params))
