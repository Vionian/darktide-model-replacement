import numpy as np

from roshia_hand_fit import retarget_thumb_to_palm


def main():
    source_palm = {
        "wrist": np.array((0.0, 0.0, 0.0)),
        "index": np.array((0.04, 0.01, 0.0)),
        "middle": np.array((0.02, 0.08, 0.0)),
        "pinky": np.array((-0.03, 0.0, 0.0)),
    }
    source_thumb = np.array((
        (-0.01, 0.01, 0.0),
        (-0.02, 0.03, 0.01),
        (-0.015, 0.055, 0.015),
    ))
    rotation = np.array(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
    scale = 1.2
    target_origin = np.array((0.2, 0.3, 0.4))
    target_palm = {
        key: target_origin + rotation @ point * scale
        for key, point in source_palm.items()
    }
    target_thumb = np.repeat((target_origin + np.array((0.0, 0.0, 0.03)))[None, :], 3, axis=0)

    fitted, report = retarget_thumb_to_palm(
        source_palm, source_thumb, target_palm, target_thumb, strength=1.0
    )
    expected = target_origin + (source_thumb @ rotation.T) * scale
    assert np.allclose(fitted, expected, atol=1e-8)
    assert abs(report["palm_scale"] - scale) < 1e-8
    source_lengths = np.linalg.norm(np.diff(source_thumb, axis=0), axis=1) * scale
    fitted_lengths = np.linalg.norm(np.diff(fitted, axis=0), axis=1)
    assert np.allclose(fitted_lengths, source_lengths, atol=1e-8)

    halfway, _ = retarget_thumb_to_palm(
        source_palm, source_thumb, target_palm, target_thumb, strength=0.5
    )
    assert np.allclose(halfway, (fitted + target_thumb) * 0.5, atol=1e-8)
    print("ROSHIA_THUMB_FIT_TEST_OK", report)


if __name__ == "__main__":
    main()
