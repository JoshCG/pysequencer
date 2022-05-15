from __future__ import annotations
from typing import List
from enum import IntEnum
import pathlib

import unreal

from pysequencer.ue_helpers import LS_BP_LIB, MSE, ATH, EAL
from pysequencer.core.nodes.node_base import AssetNode


class CameraOrder(IntEnum):
    stack = 0
    one_by_one = 1


class LevelSequenceNodeError(Exception):
    pass


class SequenceCamera:
    def __init__(self, proxy: unreal.SequencerBindingProxy):
        self._proxy = proxy
        self._sequence = LevelSequenceNode(proxy.sequence.get_full_name())
        self._start = None
        self._end = None
        self._key_frames_data = None

    @classmethod
    def import_camera(
        cls,
        fbx_path: str,
        sequence: LevelSequenceNode,
        proxy: unreal.SequencerBindingProxy = None,
        name: str = None,
        start_frame: int = None,
        new_section: bool = True,
    ) -> SequenceCamera or None:
        """
        Import Fbx Camera To Level Sequence
        :param fbx_path: camera fbx path
        :param sequence: Level Sequence Node
        :param proxy: camera binding proxy
        :param name: camera name
        :param start_frame: start frame
        :param new_section: set camera cut section
        :return: Sequence Camera object
        """
        from pysequencer.ue_helpers import ELL

        sequence.open()

        fbx_path = pathlib.Path(fbx_path)

        # import camera settings
        camera_settings = unreal.MovieSceneUserImportFBXSettings()
        camera_settings.set_editor_property("create_cameras", False)
        camera_settings.set_editor_property("force_front_x_axis", False)
        camera_settings.set_editor_property("match_by_name_only", False)
        camera_settings.set_editor_property("reduce_keys", False)

        # current world
        current_world = ELL.get_editor_world()

        # setup camera name
        if name is None:
            name = fbx_path.stem

        # if camera is not exist in sequence, add a camera actor to sequence
        cam_actor = None
        if not proxy:
            cam_actor = ELL.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector())
            cam_actor.set_actor_label(name)
            proxy = sequence.node.add_spawnable_from_instance(cam_actor)

        import_status = unreal.SequencerTools.import_level_sequence_fbx(
            current_world, sequence.node, [proxy], camera_settings, fbx_path.as_posix()
        )

        # delete camera actor
        if cam_actor:
            cam_actor.destroy_actor()

        # init SequenceCamera object
        camera = cls(proxy)
        if not import_status or camera is None:
            return

        # set camera start frame
        if start_frame:
            camera.set_start_frame(start_frame)

        # add a section set current camera
        if new_section:
            sections = camera.camera_cut_sections
            if not sections:
                sections = [sequence.camera_cut_track.add_section()]

            for section in sections:
                section.set_camera_binding_id(camera.proxy.get_binding_id())
                section.set_range(camera.start, camera.end)

        return camera

    @property
    def proxy(self) -> unreal.SequencerBindingProxy:
        return self._proxy

    @property
    def name(self) -> str:
        return str(self.proxy.get_display_name())

    @property
    def start(self) -> int:
        """
        The start frame from camera keyframes in current sequence
        """
        if self._start is None:
            self.__setup_camera_data()
        return self._start

    @property
    def end(self) -> int:
        """
        The end frame from camera keyframes in current sequence
        """
        if self._end is None:
            self.__setup_camera_data()
        return self._end

    @property
    def camera_cut_sections(self) -> List[unreal.MovieSceneCameraCutSection]:
        """
        Get camera cut sections from current sequence's camera cut track
        """
        result = list()
        camera_cut_track = self._sequence.camera_cut_track
        camera_objects = LS_BP_LIB.get_bound_objects(self.proxy.get_binding_id())

        for section in camera_cut_track.get_sections():
            if not isinstance(section, unreal.MovieSceneCameraCutSection):
                continue

            section_binding_id = section.get_camera_binding_id()
            section_objects = LS_BP_LIB.get_bound_objects(section_binding_id)
            if section_objects and section_objects == camera_objects:
                result.append(section)

        return result

    def set_start_frame(self, start: int):
        """
        Set start frame of current camera keyframes
        :param start: start frame number
        """
        offset = start - self.start

        for ch, keys in self._key_frames_data.items():
            ch_start = keys[0].get_time().frame_number.value

            sub_offset = self.start - ch_start
            for key in keys:
                current_frame = key.get_time().frame_number.value
                new_frame = current_frame + sub_offset + offset

                new_time = unreal.FrameNumber(value=new_frame)
                key.set_time(new_time)

        self.__setup_camera_data()

    def __setup_camera_data(self) -> None:
        """
        Get current camera data. include the keyframes and channels
        """

        self._key_frames_data = dict()

        start = None
        end = None

        proxies = self.proxy.get_child_possessables()
        proxies.append(self.proxy)

        for proxy in proxies:
            for track in proxy.get_tracks():
                for section in track.get_sections():
                    for ch in section.get_channels():
                        keys = ch.get_keys()
                        if keys:
                            self._key_frames_data[ch] = keys
                            key_start = keys[0].get_time().frame_number.value
                            key_end = keys[-1].get_time().frame_number.value
                            if start is None or start > key_start:
                                start = key_start
                            if end is None or end < key_end:
                                end = key_end
        self._start = start
        self._end = end

    def __repr__(self):
        return f"<SequenceCamera name={self.name} start={self.start} end={self.end}>"


class LevelSequenceNode(AssetNode):
    @property
    def start(self) -> int:
        return self.node.get_playback_start()

    @start.setter
    def start(self, frame: int):
        self.node.set_playback_start(frame)

        sec = float(frame) / float(self.fps)
        self.node.set_view_range_start(sec)
        self.node.set_work_range_start(sec)

    @property
    def end(self) -> int:
        return self.node.get_playback_end()

    @end.setter
    def end(self, frame):
        self.node.set_playback_end(frame)

        sec = float(frame) / float(self.fps)
        self.node.set_view_range_end(sec)
        self.node.set_work_range_end(sec)

    @property
    def fps(self) -> int:
        dr = self.node.get_display_rate()
        return int(dr.numerator / dr.denominator)

    @fps.setter
    def fps(self, value: int):
        dr = self.node.get_display_rate()
        dr.numerator = value
        dr.denominator = 1

        self.node.set_display_rate(dr)

    @property
    def current_frame(self) -> int:
        if self.current_level_sequence().node != self.node:
            self.open()
        return LS_BP_LIB.get_current_time()

    @current_frame.setter
    def current_frame(self, frame):
        if self.current_level_sequence().node != self.node:
            self.open()

        LS_BP_LIB.set_current_time(frame)

    @property
    def cameras(self) -> List[SequenceCamera]:
        result = list()
        for x in self.node.get_spawnables():
            if isinstance(x.get_object_template(), unreal.CineCameraActor):
                result.append(SequenceCamera(x))
        return result

    @property
    def camera_cut_track(self) -> unreal.MovieSceneCameraCutTrack:
        master_tracks = MSE.get_master_tracks(self.node)
        camera_cut_track = next((x for x in master_tracks if isinstance(x, unreal.MovieSceneCameraCutTrack)), None)
        if camera_cut_track is None:
            camera_cut_track = self.add_camera_cut_track()

        return camera_cut_track

    @classmethod
    def current_level_sequence(cls) -> LevelSequenceNode:
        sequence = LS_BP_LIB.get_current_level_sequence()

        return cls(sequence.get_full_name())

    @classmethod
    def sequence(cls, path: str, create_new: bool = True) -> LevelSequenceNode or None:
        path = pathlib.Path(path)

        if not EAL.does_asset_exist(path.as_posix()) and create_new:
            ATH.get_asset_tools().create_asset(
                asset_name=path.stem,
                package_path=path.parent.as_posix(),
                asset_class=unreal.LevelSequence,
                factory=unreal.LevelSequenceFactoryNew(),
            )
            EAL.save_asset(path.as_posix())

        if EAL.does_asset_exist(path.as_posix()):
            return cls(path.as_posix())

    def add_camera(
        self, fbx_path: str, name: str = None, start_frame: int = None, match_camera_name: bool = True
    ) -> SequenceCamera:
        """
        Import fbx camera to current level sequence
        :param fbx_path: camera fbx path
        :param name: camera name
        :param start_frame: start frame of camera keyframe
        :param match_camera_name: Is match current sequence camera track name
        :return: SequenceCamera object
        """
        fbx_path = pathlib.Path(fbx_path)

        name = name or fbx_path.stem
        camera_proxy = None

        if match_camera_name:
            camera = next((x for x in self.cameras if x.name == name), None)
            if camera:
                camera_proxy = camera.proxy

        camera = SequenceCamera.import_camera(
            fbx_path=fbx_path.as_posix(),
            sequence=self,
            proxy=camera_proxy,
            name=name,
            start_frame=start_frame,
        )

        if camera is None:
            raise LevelSequenceNodeError(f"Import camera fbx is error {fbx_path.as_posix()}")

        return camera

    def add_cameras(
        self,
        cameras: List[dict],
        start_frame: int = None,
        match_camera_name: bool = True,
        order: CameraOrder = CameraOrder.one_by_one,
        auto_frame_range: bool = True,
    ) -> List[SequenceCamera]:
        """
        Add cameras to current level sequence.
        :param cameras: A list of camera data, Item is a dict(str@camera_name=str@fbx_path)
        :param start_frame: Start frame
        :param match_camera_name: Is match current camera name in level sequence
        :param order: Cameras
        :param auto_frame_range: Auto set frame range for sequence
        :return: A list of SequenceCamera object
        """
        result = list()
        start = start_frame
        end = None

        for camera_data in cameras:
            for camera_name, camera_path in camera_data.items():
                camera = self.add_camera(
                    camera_path, camera_name, start_frame=start_frame, match_camera_name=match_camera_name
                )

                if camera:
                    start_frame = camera.end + 1 if order == order.one_by_one else start_frame
                    result.append(camera)
                    if auto_frame_range:
                        if end is None or order == CameraOrder.one_by_one:
                            end = camera.end
                        elif end < camera.end:
                            end = camera.end
                break

        if auto_frame_range:
            self.start = start
            self.end = end

        return result

    def clear_cameras(self):
        # todo fixed crash
        for camera in self.cameras:
            for child in camera.proxy.get_child_possessables():
                child.remove()
            camera.proxy.remove()

    def add_camera_cut_track(self) -> unreal.MovieSceneCameraCutTrack:
        """
        Add master camera cut track
        """
        return self._add_track(unreal.MovieSceneCameraCutTrack)

    def _add_track(self, track_type):
        return self.node.add_master_track(track_type)
