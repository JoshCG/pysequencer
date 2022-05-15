from typing import List
from pysequencer.core.nodes import LevelSequenceNode, CameraOrder, SequenceCamera


def create_sequence(path: str) -> LevelSequenceNode:
    return LevelSequenceNode.sequence(path, create_new=True)


def import_camera(fbx_path: str, sequence_path: str, camera_name: str = None, start_frame: int = None):
    level_sequence = LevelSequenceNode.sequence(sequence_path, create_new=True)

    camera = level_sequence.add_camera(fbx_path=fbx_path, name=camera_name, start_frame=start_frame)

    assert isinstance(camera, SequenceCamera)


def import_cameras(fbx_data: List[dict], sequence_path: str, start_frame: int, order=CameraOrder.one_by_one):
    level_sequence = LevelSequenceNode.sequence(sequence_path, create_new=True)

    cameras = level_sequence.add_cameras(cameras=fbx_data, start_frame=start_frame, order=order)

    for camera in cameras:
        assert isinstance(camera, SequenceCamera)


if __name__ == "__main__":
    sequence_path = "/Game/Shots/Test/LS_Test_Main"

    # get sequence
    sequence = create_sequence(sequence_path)

    # import one camera, the keyframe start at 1001
    shot_0010_fbx_path = r"C:\Users\joshc\Desktop\test.cameras\shot0010_camera_1_150_fps30.fbx"
    import_camera(shot_0010_fbx_path, sequence_path, camera_name="shot_0010", start_frame=1001)

    # import cameras
    camera_data = [
        {"shot_0010": shot_0010_fbx_path},
        {"shot_0020": r"C:\Users\joshc\Desktop\test.cameras\shot0020_camera_10_50_fps30.fbx"},
    ]

    # import_cameras(camera_data, sequence_path, 1001, order=CameraOrder.one_by_one)

    import_cameras(camera_data, sequence_path, 1001, order=CameraOrder.stack)
