"""Use the existing schemas with either desktop Pydantic 2 or Android's pure Python runtime.

The Android runtime has no Pydantic Core binary. The compatibility layer keeps
the same declarations and invokes every existing after-validator. It is tested
against the desktop schemas; it does not replace validation with dictionaries.
"""
import pydantic

if not pydantic.VERSION.startswith('1.'):
    from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator
else:
    import json
    import math
    import typing
    from pydantic import ValidationError, root_validator, validator
    from pydantic.fields import FieldInfo, Undefined, SHAPE_SINGLETON, SHAPE_DICT, SHAPE_MAPPING
    from pydantic.main import ModelMetaclass

    ConfigDict = dict

    def Field(default=Undefined, **kwargs):
        if 'pattern' in kwargs:
            kwargs['regex'] = kwargs.pop('pattern')
        return pydantic.Field(default, **kwargs)

    class _JsonValue:
        @classmethod
        def __get_validators__(cls):
            yield cls.validate

        @classmethod
        def validate(cls, value):
            if value is None or type(value) in (str, bool, int):
                return value
            if type(value) is float and math.isfinite(value):
                return value
            if isinstance(value, list):
                return [cls.validate(item) for item in value]
            if isinstance(value, dict) and all(isinstance(key, str) for key in value):
                return {key: cls.validate(item) for key, item in value.items()}
            raise ValueError('JSON value must be finite and contain only JSON types')

    JsonValue = typing.Optional[_JsonValue]

    class CompatibilityMeta(ModelMetaclass):
        def __new__(mcls, name, bases, namespace, **kwargs):
            namespace.pop('model_config', None)
            for key, annotation in namespace.get('__annotations__', {}).items():
                field = namespace.get(key)
                sequence = typing.get_origin(annotation) is list or (
                    isinstance(annotation, str) and annotation.startswith('list['))
                if isinstance(field, FieldInfo) and sequence:
                    field.min_items, field.min_length = field.min_length, None
                    field.max_items, field.max_length = field.max_length, None
            return super().__new__(mcls, name, bases, namespace, **kwargs)

    def model_validator(*, mode):
        if mode != 'after':
            raise ValueError('Only the audited after-validation interface is supported')

        def decorate(function):
            def validate(cls, values):
                function(cls.construct(**values))
                return values
            validate.__name__ = function.__name__
            validate.__qualname__ = function.__qualname__
            return root_validator(allow_reuse=True, skip_on_failure=True)(validate)
        return decorate

    def validate_types(field, value):
        if value is None:
            return
        if field.shape in (SHAPE_DICT, SHAPE_MAPPING):
            if isinstance(value, dict):
                for key, item in value.items():
                    if field.key_field:
                        validate_types(field.key_field, key)
                    for sub in field.sub_fields or []:
                        validate_types(sub, item)
            return
        if field.shape != SHAPE_SINGLETON:
            if isinstance(value, (list, tuple)):
                for item in value:
                    for sub in field.sub_fields or []:
                        validate_types(sub, item)
            return
        kind = field.type_
        if isinstance(kind, type):
            if issubclass(kind, str) and not isinstance(value, str):
                raise ValueError('Text fields require a string')
            if issubclass(kind, int) and not issubclass(kind, bool):
                if isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
                    raise ValueError('Integer fields cannot truncate fractional values')

    class BaseModel(pydantic.BaseModel, metaclass=CompatibilityMeta):
        class Config:
            extra = 'forbid'
            allow_inf_nan = False
            smart_union = True

        @validator('*', pre=True, allow_reuse=True)
        def preserve_input_types(cls, value, field):
            validate_types(field, value)
            return value

        @classmethod
        def model_validate(cls, value):
            return value if isinstance(value, cls) else cls.parse_obj(value)

        @classmethod
        def model_validate_json(cls, value):
            return cls.model_validate(json.loads(value))

        def model_dump(self, **kwargs):
            def without_conditional_nulls(value):
                if isinstance(value, dict):
                    return {key: without_conditional_nulls(item) for key, item in value.items()
                            if not (key == 'generatedTrack' and item is None)}
                if isinstance(value, (list, tuple)):
                    return [without_conditional_nulls(item) for item in value]
                return value
            return without_conditional_nulls(self.dict(**kwargs))

__all__ = ['BaseModel', 'ConfigDict', 'Field', 'JsonValue', 'ValidationError', 'model_validator']
