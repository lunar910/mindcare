"""Pose presets. Owner: the pose / behaviour pass.
World frame: Z up, metres. The sofa runs along X against the back wall; its seat top is at z = room_bl.SEAT_Z (0.43),
the seat front edge at y = 0.82, the back cushions' front face at about y = 1.42. The camera side is -Y. Floor at z = 0."""
POSES = {
    'seated': dict(
        hip=(0.0, 1.22, 0.525), feet_spread={'L': 0.13, 'R': 0.16}, feet_fwd=0.4, shin_drop=0.44,
        lean=-8, twist=6, head_yaw=-8, head_pitch=5, head_roll=-4, gaze=(0.0, -1.0, 1.15),
        arms={'L': dict(mode='rest', wrist=(0.5, 1.47, 0.985), hand_dir=(1, 0.15, -0.2), pole=(0.25, 0.7, 0.5), curl=0.5),
              'R': dict(mode='knee', pole=(-0.85, 0.45, -0.2), curl=0.85)}),
}
