# -*- coding:utf8 -*-

import json
from jinja2 import Template

from jinja2 import Environment, Undefined


def def_name_filters():

    def variable_name(name):
        return 'tttt_%s' % name

    env = Environment()
    env.filters['var_name'] = variable_name

def render_header(models):
    content = open('objc_header.template').read()
    template = Template(content)
    print template.render(models=models)

def render_body(models):
    pass

def to_camel_case(s, lower=True):
    import re
    return re.sub(r'(?!^)_([a-zA-Z])', lambda m: m.group(1).upper(), s) if s else s

def process_property_names(models):
    for m in models:
        for p in m['properties']:
            p['name'] = to_camel_case(p['name'])

def flatten_models(models):
    return[m for (name, m) in models.items()]


def process_ref_types(p, models):
    t = p['type']
    if t.startswith('#/definitions'):
        t = t.replace('#/definitions/', '')
        t = models[t]['name']
        p['type'] = t


def process_property_types(models):
    for (name, m) in models.items():
        for p in m.get('properties', []):
            process_ref_types(p, models)
            items = p.get('items', None) 
            if items:
                process_ref_types(items, models)
            enum = p.get('enum', None)
            if enum:
                p['comment'] = '%s' % '\n'.join(enum)
    return models

def convert_to_objc_type(p):
    if not p: return (None, False, False)

    t = p['type']

    item_type, _, _ = convert_to_objc_type(p.get('items', {}))
    m = {
            'int32': ('int', True, True),
            'int64': ('long long', True, True),
            'float': ('float', True, True),
            'double': ('double', True, True),
            'boolean': ('BOOL', True, True),
            'string': ('NSString', False, True),
            'date': ('NSString', False, True),
            'date-time': ('NSString', False, True),
            'array': ('NSArray<%s *>' % item_type, False, False),
            'byte': ('NSData', False, False),
            'binary': ('NSData', False, False),
            }
    return m.get(t, (t, False, False))


def convert_to_objc_types(models):
    for (name, m) in models.items():
        for p in m.get('properties', []):
            t, is_native_type, is_simple_type = convert_to_objc_type(p)
            p['type'] = t
            p['is_native_type'] = is_native_type
            p['is_simple_type'] = is_simple_type
    return models


"""
    boolean/int32/int64/float/double/string/date/date-time/array
"""
def parse_property(name, definition):
    if not definition:
        return None

    t = definition.get('type', None)
    if 'format' in definition:
        t = definition['format']

    if '$ref' in definition:
        t = definition['$ref']

    items = parse_property('items', definition.get('items', None))
    enum = definition.get('enum', None)

    return {
            'name': name,
            'type': t,
            'example': definition.get('example', None),
            'items': items,
            'enum': enum,
            }

def parse_model(model_name, definition):
    props = []
    required_props = definition.get('required', [])
    for (name, p) in definition.get('properties', {}).items():
        prop = parse_property(name, p)
        prop['required'] = name in required_props
        props.append(prop)
    return { 'name': model_name,
             'properties': props }


def parse_definitions(definitions):
    models = {}
    for (name, d) in definitions.items():
        models[name] = parse_model(name, d)
    return models


def main(path):
    model = { 
            'name': 'Person',
            'properties': [
                {
                'name': 'test_gender',
                'type': 'NSInteger',
                'is_native_type': True,
                'comment': 'hello',
                },
                {
                'name': 'test_name',
                'type': 'NSString',
                'is_simple_type': True,
                'comment': 'hello',
                },
                {
                'name': 'test_books',
                'type': 'NSArray<Book *>',
                'comment': 'hello',
                },
                ],
            }
    models = [model]
    process_property_names(models)
    render_header(models)

    content = json.load(open(path))
    for key in content:
        print key

    parsed_models = parse_definitions(content['definitions'])
    parsed_models = process_property_types(parsed_models)
    parsed_models = convert_to_objc_types(parsed_models)
    parsed_models = flatten_models(parsed_models)
    process_property_names(parsed_models)
    render_header(parsed_models)

if __name__ == '__main__':
    import sys
    main(sys.argv[1])
