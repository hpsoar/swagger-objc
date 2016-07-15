# -*- coding:utf8 -*-

import json
from jinja2 import Template

from jinja2 import FileSystemLoader
from jinja2.environment import Environment
jenv = Environment()
jenv.loader = FileSystemLoader('.')


class Property(object):
    def __init__(self, name, info):
        self.type = ''
        self.item_type = None
        self.parse(name, info)

    """
        boolean/int32/int64/float/double/string/date/date-time/array
    """
    def parse(self, name, definition):
        if not definition:
            return None

        if not name:
            name = definition.get('name', None)
        self.name = name

        definition.update(definition.get('schema', {}))
    
        t = definition.get('type', None)
        if 'format' in definition:
            t = definition['format']
    
        if '$ref' in definition:
            t = definition['$ref']

        self.type = t

        self.required = definition.get('required', False)
    
        self.default = definition.get('default', None)
        self.item_type = Property('item_type', definition.get('items', None))
        self.enum = definition.get('enum', None)
        self.example = definition.get('example', None)
        self.examples = definition.get('examples', None)
        self.comment = ''
        self.desc = definition.get('description', None)
        self.is_native_type = False
        self.is_simple_type = False


class Parameter(Property):
    def __init__(self, name, info):
        super(Parameter, self).__init__(name, info)
        self.desc = info.get('description', '')
        self.position = info.get('in', 'query')
    

class API:
    def __init__(self, name, path, method, parameters, responses, summary, desc, tags):
        self.name = name
        self.path = path
        self.method = method
        self.parameters = parameters
        self.responses = responses
        self.summary = summary
        self.desc = desc
        self.tags = tags


def render_models(models, template):
    template = jenv.get_template(template)
    print template.render(models=models)


def render_header(models):
    render_models(models, 'objc_header.template')


def render_body(models):
    render_models(models, 'objc_body.template')


def to_camel_case(s, lower=True):
    import re
    ret = re.sub(r'(?!^)_([a-zA-Z])', lambda m: m.group(1).upper(), s) if s else s
    if not lower:
        ret = ret[0].upper() + ret[1:] if ret else ret
    return ret


def convert_property_name(name):
    if name == 'id':
        return 'Id'
    else:
        return to_camel_case(name)


def flatten_models(models):
    return[m for (name, m) in models.items()]


def process_ref_types(p, models):
    if p.type and p.type.startswith('#/definitions'):
        t = p.type.replace('#/definitions/', '')
        p.type = models[t]['name']


def process_property(p, models):
    process_ref_types(p, models)
    if p.item_type:
        process_ref_types(p.item_type, models)
    if p.enum:
        p.comment = '%s' % '\n'.join(p.enum)
    p.name = convert_property_name(p.name)


def process_model_properties(models):
    for (name, m) in models.items():
        for p in m.get('properties', []):
            process_property(p, models)
    return models


def convert_to_objc_type(p):
    if not p: return (None, False, False, None)

    convert_to_objc_type(p.item_type)
    m = {
            'int32': ('int', True, True),
            'int64': ('long long', True, True),
            'float': ('float', True, True),
            'double': ('double', True, True),
            'boolean': ('BOOL', True, True),
            'string': ('NSString', False, True),
            'date': ('NSString', False, True),
            'date-time': ('NSString', False, True),
            'array': ('NSArray', False, False),
            'byte': ('NSData', False, False),
            'binary': ('NSData', False, False),
            }
    t, is_native_type, is_simple_type = m.get(p.type, (p.type, False, False))
    p.type = t
    p.is_native_type = is_native_type
    p.is_simple_type = is_simple_type
    p.item_type = p.item_type and p.item_type.type


def convert_to_objc_types(models):
    for m in models:
        for p in m.get('properties', []):
            convert_to_objc_type(p)
    return models


def parse_model(model_name, definition):
    props = []
    required_props = definition.get('required', [])
    for (name, p) in definition.get('properties', {}).items():
        prop = Property(name, p)
        if not prop.required:
            prop.required = name in required_props
        props.append(prop)
    return { 'name': model_name,
             'properties': props }


def parse_definitions(definitions):
    models = {}
    for (name, d) in definitions.items():
        models[name] = parse_model(name, d)
    return models


def process_api_names(apis):
    for api in apis:
        api.name = to_camel_case(api.name, lower=False)
    return apis


def process_api_parameters(apis, models):
    for api in apis:
        for p in api.parameters:
            process_property(p, models)
    return apis


def process_api_responses(apis, models):
    for api in apis:
        for p in api.responses:
            process_property(p, models)
    return apis


def convert_api_to_objc(apis):
    for api in apis:
        for p in api.parameters:
            convert_to_objc_type(p)
        for p in api.responses:
            convert_to_objc_type(p)
    return apis


def parse_api(paths):
    apis = []
    for (path, ops) in paths.items():
        for (method, api_info) in ops.items():
            parameters = [Parameter(None, p) for p in api_info.get('parameters', [])]
            responses = [Property(code, info) for (code, info) in api_info.get('responses', {}).items()]
            api = API(api_info.get('operationId', ''), 
                    path, 
                    method,
                    parameters,
                    responses, 
                    api_info.get('summary', ''),
                    api_info.get('description', ''),
                    api_info.get('tags', []))
            apis.append(api)

    return apis


def render_apis(apis):
    template = jenv.get_template('objc_api.template')
    print template.render(apis=apis)


def render_api_options(apis):
    pass


def main(path):
    content = json.load(open(path))
    for key in content:
        print key

    parsed_models = parse_definitions(content['definitions'])
    parsed_models = process_model_properties(parsed_models)

    apis = parse_api(content.get('paths', {}))
    apis = process_api_names(apis)
    apis = process_api_parameters(apis, parsed_models)
    apis = process_api_responses(apis, parsed_models)
    apis = convert_api_to_objc(apis)

    parsed_models = flatten_models(parsed_models)
    parsed_models = convert_to_objc_types(parsed_models)
    render_header(parsed_models)
    render_body(parsed_models)

    render_api_options(apis)
    render_apis(apis)

if __name__ == '__main__':
    import sys
    main(sys.argv[1])
