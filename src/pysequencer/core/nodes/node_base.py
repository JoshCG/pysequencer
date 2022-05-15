from typing import List
from pysequencer.ue_helpers import AES, EAL

from pysequencer.core.node_caches import NodeCache, PropertyCategory, NodeCacheProperty, ETL


class NodeError(Exception):
    pass


class NodeMissAttr:
    pass


class NodeBase:
    def __init__(self, node_type: str = None):
        self.node_type = node_type
        self._ins_cache = NodeCache(node_type)
        self._node = None

    @property
    def node(self):
        return self._node

    @property
    def editor_property_names(self) -> List[str]:
        return self._ins_cache.editor_property_names

    @property
    def class_property_names(self) -> List[str]:
        return self._ins_cache.class_property_names

    @property
    def doc(self) -> str:
        return self._ins_cache.doc

    def __getattr__(self, item):
        ins = getattr(self, item, NodeMissAttr)
        if ins is NodeMissAttr:
            ins = getattr(self._node, item, NodeMissAttr)

        if ins is NodeMissAttr:
            return super(NodeBase, self).__getattr__(item)
        else:
            return ins

    def property(self, name: str, property_category: PropertyCategory = PropertyCategory.EDITOR) -> NodeCacheProperty:
        p = self._ins_cache.property_by_name(name, property_category)
        return NodeCacheProperty(p, self._node)

    def __repr__(self):
        cls_name = self.__class__.__name__
        return f"<{cls_name}: type={self.node_type}, node={str(self._node)}>"


class AssetNode(NodeBase):
    def __init__(self, path: str):
        """
        Init Asset Node.
        :param path: Asset content path
        """
        self._path = path
        asset = self.asset_from_path(path)
        node_type = asset.get_class().get_name()
        super().__init__(node_type=node_type)

        self._node = asset

    @staticmethod
    def asset_from_path(path: str):
        """
        Get a unreal engine asset object from content path
        :param path: Asset content path
        :return: unreal asset object
        """
        asset = ETL.load_asset(asset_path=path)

        if asset is None:
            raise NodeError(f"Asset is not exist: {path}")

        return asset

    def open(self):
        """
        Open asset editor
        :return:
        """
        AES.open_editor_for_assets([self.node])

    def close(self):
        """
        Close asset editor
        :return:
        """
        AES.close_all_editors_for_asset(self.node)

    def exist(self) -> bool:
        """
        Current asset is exist.
        :return:
        """
        return EAL.does_asset_exist(self._path)


class ActorNode(NodeBase):
    # todo Actor
    pass
