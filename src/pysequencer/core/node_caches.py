from typing import List
from enum import IntEnum
import re

import unreal

ETL = unreal.EditorAssetLibrary()

CACHE_CLASSES = ("LevelSequence", "StaticMesh", "Blueprint")


def find_matches(pattern: str, source: str) -> list or None:
    finders = re.findall(pattern, source, re.MULTILINE)
    return finders


def find_groups(pattern: str, source: str) -> list:
    result = list()

    for match in re.finditer(pattern, source, re.MULTILINE):
        result.append(match.groupdict())

    return result


class PropertyCategory(IntEnum):
    EDITOR = 0
    CLASS = 1


class NodeCacheError(Exception):
    pass


class PropertyTypeSingleton(type):
    __CACHE_DATA = dict()

    def __call__(cls, *args, **kwargs):
        property_type = args[0] if args else kwargs.get("property_type", None)

        if property_type not in cls.__CACHE_DATA:
            cls.__CACHE_DATA[property_type] = super(PropertyTypeSingleton, cls).__call__(*args, **kwargs)

        return cls.__CACHE_DATA[property_type]


class PropertyType(metaclass=PropertyTypeSingleton):
    def __init__(self, property_type: str):
        self.name = property_type
        self._type = None

    @property
    def type(self):
        if self._type is None:
            ins_type = None

            if self.name == "bool":
                ins_type = bool
            elif self.name == "int32":
                ins_type = int
            elif self.name == "float":
                ins_type = float
            elif self.name.startswith("Array("):
                pattern = r"Array\((?P<sub_type>.+)\)"
                groups = find_groups(pattern, self.name)
                if groups:
                    sub_type = getattr(unreal, groups[0]["sub_type"], None)
                    if sub_type is not None:
                        ins_type = List[sub_type]
            else:
                ins_type = getattr(unreal, self.name, None)

            if ins_type is not None:
                self._type = ins_type

        return self._type

    def __repr__(self):
        return f"<Property Type: {self.name}, {self.type}>"


class PropertyError(Exception):
    pass


class NodeCachePropertyBase:
    def __init__(self, name: str, property_type: str, permission: str, des: str, parent: unreal.Object):
        self.name = name
        self.property_type = PropertyType(property_type)
        self.permission = permission
        self.des = des

        self.parent = parent

        self._is_write = None

    @property
    def is_write(self) -> bool:
        if self._is_write is None:
            self._is_write = "Write" in self.permission

        return self._is_write

    def __repr__(self):
        body = f"{self.name} Type: {self.property_type.name}, Permission: {self.permission}, Parent={self.parent}"
        return f"<Property name: {body}>"


class NodeCacheEditorProperty(NodeCachePropertyBase):
    def __init__(self, *args, **kwargs):
        super(NodeCacheEditorProperty, self).__init__(*args, **kwargs)
        self.category = PropertyCategory.EDITOR

    def get(self, subject):
        return subject.get_editor_property(self.name)

    def set(self, value, subject):
        if self.is_write:
            return subject.set_editor_property(self.name, value)

        raise PropertyError(f"Property {self.name} is {self.permission}")


class NodeCacheClassProperty(NodeCachePropertyBase):
    def __init__(self, *args, **kwargs):
        super(NodeCacheClassProperty, self).__init__(*args, **kwargs)
        self.category = PropertyCategory.CLASS

    def get(self, subject):
        return getattr(subject, self.name, None)

    def set(self, value, subject):
        if self.is_write:
            return setattr(subject, self.name, value)

        raise PropertyError(f"Property {self.name} is {self.permission}")


class PropertySingleton(type):
    __CACHE_DATA = dict()

    def __call__(cls, *args, **kwargs):
        ins = args[0] if args else kwargs.get("property_ins", None)
        subject = args[1] if args else kwargs.get("subject", None)

        key = f"{id(subject)}_{ins.name}_{ins.category}"
        if key not in cls.__CACHE_DATA:
            cls.__CACHE_DATA[key] = super(PropertySingleton, cls).__call__(*args, **kwargs)

        return cls.__CACHE_DATA[key]


class NodeCacheProperty(metaclass=PropertySingleton):
    def __init__(self, property_ins: NodeCacheEditorProperty or NodeCacheClassProperty, subject):
        self._property = property_ins
        self._subject = subject

    @property
    def name(self) -> str:
        return self._property.name

    @property
    def property_type(self):
        return self._property.property_type

    @property
    def permission(self) -> str:
        return self._property.permission

    def get(self):
        return self._property.get(self._subject)

    def set(self, value):
        return self._property.set(value, self._subject)

    def __repr__(self):
        body = f"property: {self.name}, path={self._subject.get_path_name()}"
        return f"<NodeCacheProperty {body} {id(self)}>"


class NodeCacheSingleton(type):
    __CACHE_DATA = dict()

    def __call__(cls, *args, **kwargs):
        node_type = args[0] if args else kwargs.get("node_type", None)
        if node_type is None or not getattr(unreal, node_type, None):
            raise NodeCacheError("node_type is missing...")

        if node_type not in cls.__CACHE_DATA:
            cls.__CACHE_DATA[node_type] = super(NodeCacheSingleton, cls).__call__(*args, **kwargs)

        return cls.__CACHE_DATA[node_type]


class NodeCache(metaclass=NodeCacheSingleton):
    def __init__(self, node_type: str):
        self.node_type = node_type

        self._node_cls = getattr(unreal, node_type)
        self._doc = None
        self._des = None
        self._source_data = None
        self._editor_properties = None
        self._editor_property_names = None
        self._class_properties = None
        self._class_property_names = None

    @property
    def doc(self) -> str:
        if self._doc is None:
            self._doc = self._node_cls.__doc__

        return self._doc

    @property
    def description(self) -> str:
        if self._des is None:
            finders = find_matches(pattern=r"[^(**)]+[\.]", source=self.doc)
            if finders:
                self._des = finders[0]

        return self._des

    @property
    def source_data(self) -> dict:
        if self._source_data is None:
            result = dict()
            pattern = r"- \*\*(?P<name>\w+)\*\*: (?P<value>[\w.]+)"
            for group in find_groups(pattern=pattern, source=self.doc):
                result[group["name"]] = group["value"]
            if result:
                self._source_data = result

        return self._source_data

    @property
    def editor_property_names(self) -> List[str]:
        if self._editor_property_names is None:
            self._editor_property_names = [x.name for x in self.editor_properties]
        return self._editor_property_names

    @property
    def editor_properties(self) -> List[NodeCacheEditorProperty]:
        if self._editor_properties is None:
            result = list()
            pattern = r"- ``(?P<name>\w+)`` \((?P<property_type>[\w()]+)\):  \[(?P<permission>[\w-]+)\] (?P<des>[\w ,'().\n\r-]+)$"
            for group in find_groups(pattern=pattern, source=self.doc):
                result.append(NodeCacheEditorProperty(parent=self, **group))
            if result:
                self._editor_properties = result

        return self._editor_properties

    @property
    def class_property_names(self) -> List[str]:
        if self._class_property_names is None:
            self._class_property_names = [x.name for x in self.class_properties]

        return self._class_property_names

    @property
    def class_properties(self) -> List[NodeCacheClassProperty]:
        if self._class_properties is None:
            result = list()

            for attr in dir(self._node_cls):
                if attr.startswith("__"):
                    continue

                attr_obj = getattr(self._node_cls, attr)

                if type(attr_obj).__name__ != "getset_descriptor":
                    continue

                pattern = r"\((?P<property_type>\w+)\):  \[(?P<permission>[\w-]+)\] (?P<des>[\w ,'().\n\r\/:-]+)"

                for group in find_groups(pattern=pattern, source=attr_obj.__doc__):
                    group["name"] = attr
                    group["parent"] = self
                    result.append(NodeCacheClassProperty(**group))

                if result:
                    self._class_properties = result

            return self._class_properties

    def property_by_name(
        self, name: str, property_category: PropertyCategory = PropertyCategory.EDITOR
    ) -> NodeCacheEditorProperty or NodeCacheClassProperty:
        if property_category == PropertyCategory.EDITOR:
            pool = self.editor_properties
            names = self.editor_property_names
        else:
            pool = self.class_properties
            names = self._class_property_names

        if name in names:
            index = names.index(name)
            return pool[index]

    def __repr__(self):
        return f"<{self.__class__.__name__} Type: {self.node_type}>"


def _generate_default_caches():
    for name in CACHE_CLASSES:
        NodeCache(name)


_generate_default_caches()
