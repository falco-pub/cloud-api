#!/usr/bin/python3

import ovh
import os
from configparser import RawConfigParser, NoOptionError

CONFIG_PATH = [
    '/etc/ovh.conf',
    os.path.expanduser('~/.ovh.conf'),
    os.path.realpath('./ovh.conf'),
]


class ConfigMgr(object):
    """
    Application wide configuration manager
    """
    def __init__(self):
        """
        Create a config parser and load from environment
        """
        self.config = RawConfigParser()
        self.config.read(CONFIG_PATH)

    def get(self, section, name):
        """
        Returns either the value of 'OVH_***' env variable,
        or the value found in the CONFIG_PATH file
        """

        # 1/ try env
        try:
            return os.environ['OVH_'+name.upper()]
        except KeyError:
            pass

        # 2/ try from specified section/enpoint
        try:
            return self.config.get(section, name)
        except NoOptionError:
            pass

        # not found, sorry
        return None

    def read(self, config_file):
        """Read another config file"""
        self.config.read(config_file)


config = ConfigMgr()


def projects(config_file=None, *args, **kwargs):
    connect = ovh.Client(config_file=config_file, *args, **kwargs)
    result = dict()
    for p in connect.get('/cloud/project'):
        project = connect.get(f'/cloud/project/{p}')
        result[project['description']] = project
    return result


# noinspection PyMethodParameters
def indict_filter(f):
    """
    This is a decorator
    The new function will have a special treatment of
    the 'filter' argument, which has to be a dict()
    The result of the parent function will be compared
    to the 'filter' content.
    The new function only returns the list containing the dicts that
    match the criteria given by 'filter'
    """

    # noinspection PyCallingNonCallable,PyShadowingBuiltins
    def inner(self, *args, **kwargs):

        # 'filter' is None if 'filter' not in kwargs
        filter = kwargs.get('filter')
        if 'filter' in kwargs:
            del kwargs['filter']

        dictlist = f(self, *args, **kwargs)

        if not dictlist:
            return dictlist

        def _filter(input_dict, ref_dict):
            for k, v, in ref_dict.items():
                if not (v is None) and (input_dict[k] != v):
                    return False
            return True

        if filter:
            r = [x for x in dictlist if _filter(x, filter)]
        else:
            r = dictlist
        if r:
            return r
        else:
            raise LookupError(
                f"Dict not found with the {filter} filter.")

    return inner


# noinspection PyProtectedMember,PyShadowingBuiltins,PyArgumentList,PyPep8Naming
class MyCloud(ovh.Client):
    """
    A surcharge of the OVH API client,
    dedicated to a single "public cloud" project on OVH.
    Every API use '${endpoint}/cloud/{project_name}/...' URI.
    """
    def __init__(self, project=None, serviceName=None, sshKeyId=None,
                 region=None, flavor=None, image=None, config_file=None,
                 *args, **kwargs):
        """
        Constructs the ovh.Client object with other attributes
        """
        super().__init__(*args, config_file=config_file, **kwargs)

        # Load a custom config file if requested
        if config_file is not None:
            config.read(config_file)

        # Finds the project name and id, given the args or the config file
        _projects = projects(config_file)
        if serviceName:
            # Search for servicename (project id) in the list of projects
            for k, v in _projects.items():
                if v['project_id'] == serviceName:
                    project = k
                    break
            if not project:
                raise LookupError(f"Project not found, serviceName: {serviceName}")
            self._project = project
        else:
            # Guess servicename from the given project name
            self._project = project or config.get('default', 'project')
            try:
                serviceName = _projects[self._project]['project_id']
            except KeyError:
                raise KeyError(f"Project not found, name: {self._project}")

        if not config.config.has_section(self._project):
            raise LookupError(f"Section not in config file: {self._project}")

        self._serviceName = serviceName
        self._projectUri = '/cloud/project/' + self._serviceName + '/'
        self._sshKeyId = \
            sshKeyId or config.get(self._project, 'sshKeyId')
        self._default_region = \
            region or config.get(self._project, 'default_region')
        self._default_flavor = \
            flavor or config.get(self._project, 'default_flavor')
        self._default_image = \
            image or config.get(self._project, 'default_image')

    def _get(self, method, *args, **kwargs):
        """GET ${endpoint}/cloud/{project_name}/${method}"""
        return super().get(self._projectUri + method, *args, **kwargs)

    def _put(self, method, *args, **kwargs):
        """PUT ${endpoint}/cloud/{project_name}/${method}"""
        return super().put(self._projectUri + method, *args, **kwargs)

    def _post(self, method, *args, **kwargs):
        """POST ${endpoint}/cloud/{project_name}/${method}"""
        return super().post(self._projectUri + method, *args, **kwargs)

    def _delete(self, method, *args, **kwargs):
        """DELETE ${endpoint}/cloud/{project_name}/${method}"""
        return super().delete(self._projectUri + method, *args, **kwargs)

    @indict_filter
    def f_get(self, method='instance', *args, **kwargs):
        """
        GET ${endpoint}/cloud/{project_name}/${method}
        Filter the results against the "filter" argument
        """
        return super().get(self._projectUri + method, *args, **kwargs)

    # Same than: f_get('flavor', ...)
    @indict_filter
    def flavor(self):
        return self._get('flavor')

    # Same than: f_get('image', ...)
    @indict_filter
    def image(self):
        return self._get('image')

    # Same than: f_get('instance', ...)
    @indict_filter
    def instance(self):
        return self._get('instance')

    # Same than: f_get('volume', ...)
    @indict_filter
    def volume(self):
        return self._get('volume')

    def id_by_name(self, method, name=None):
        """
        Find the `id` of the object called by name `name`
        """
        try:
            items = self.f_get(method, filter={'name': name})
        except LookupError:
            return []
        id_list = [item['id'] for item in items]
        return id_list

    def id_instance_by_name(self, name=None):
        """
        Find the `id` of the instance called by name `name`
        """
        return self.id_by_name('instance', name)

    def id_volume_by_name(self, name=None):
        """
        Find the `id` of the volume called by name `name`
        """
        return self.id_by_name('volume', name)

    def get_by_ref(self, method, ref):
        """
        Returns the object called by id `ref` or by name `ref`
        """
        try:
            return self._get(f'{method}/{ref}')
        except ovh.APIError:
            id_list = self.id_by_name(method, ref)
            if len(id_list) == 1:
                return self._get(f"{method}/{id_list[0]}")
            elif len(id_list) > 1:
                raise LookupError(f"More than 1 id: {id_list}")
            else:
                raise LookupError(f"No '{method}' of id or name '{ref}'")

    def get_instance(self, ref):
        """
        Returns the `instance` called by id or by name `ref`
        """
        return self.get_by_ref('instance', ref)

    def get_volume(self, ref):
        """
        Returns the `volume` called by id or by name `ref`
        """
        return self.get_by_ref('volume', ref)

    def list_instances(self):
        return [i['name'] for i in self.instance()]

    def list_volumes(self):
        return [i['name'] for i in self.volume()]

    def delete_by_ref(self, method, ref):
        """
        Delete the object called by id or by name `ref`
        """
        try:
            return self._delete(f"{method}/{ref}")
        except ovh.APIError:
            id_list = self.id_by_name(method, ref)
            deleted = []
            for i in id_list:
                self._delete(f"{method}/{i}")
                deleted.append(i)
            return deleted

    def delete_instance(self, ref):
        return self.delete_by_ref('instance', ref)

    def delete_volume(self, ref):
        return self.delete_by_ref('volume', ref)

    def show_volumes(self):
        """
        Returns a list of volumes with their name, id, and hosts
        """
        volumes = self._get('volume')
        result = []
        for v in volumes:
            # List, in each v(olume), the name(s) of the host
            attached = [self._get(f'instance/{ins}')['name']
                        for ins in v['attachedTo']]
            if not attached:
                attached = None
            result.append(
                {'name': v['name'], 'id': v['id'], 'hosts': attached}
            )

        return result

    def show_ip(self):
        """
        Returns a list of hostnames and their main IP address
        """
        result = []
        for instance in self.f_get('instance', filter={'status': 'ACTIVE'}):
            name = instance['name']
            ipv4 = None
            for ip in instance['ipAddresses']:
                if ip['version'] == 4 and ip['type'] == 'public':
                    ipv4 = ip['ip']
            result.append({name: ipv4})

        return result

    def new_volume(self, region=None, size=None, type='classic', name=None):
        region = region or self._default_region
        """Creates a new volume"""
        if not isinstance(size, int):
            raise TypeError("'size' should be integer!")
        print(f"Create in : region={region}, size={size}, type={type}")
        return self._post(
            'volume', region=region, size=size, type=type, name=name
        )

    def new_instance(self, flavor=None, region=None, name=None, image=None):
        """Creates a new instance"""
        # Find the id's of the flavor and image in the region
        flavor = flavor or self._default_flavor
        image = image or self._default_image
        region = region or self._default_region
        sshKeyId = self._sshKeyId
        flavorId = \
            self.flavor(filter={'name': flavor, 'region': region})[0]['id']
        imageId = self.image(filter={'name': image, 'region': region})[0]['id']
        print(f'image: {imageId}, flavor: {flavorId}')
        return self._post('instance', flavorId=flavorId, imageId=imageId,
                          name=name, region=region, sshKeyId=sshKeyId)

    def attach_volume(self, instance_name, volume_name):
        """
        Attach volume of name /volume_name/ to instance of name /instance_name/
        """
        instance_id = self.get_instance(instance_name)['id']
        volume_id = self.get_volume(volume_name)['id']
        print(f"v:{volume_id}, i:{instance_id}")
        return self._post(f'volume/{volume_id}/attach',
                          instanceId=instance_id,
                          )

    def detach_volume(self, instance_name, volume_name):
        """
        Detach volume of /volume_name/ from instance of /instance_name/
        """
        instance_id = self.get_instance(instance_name)['id']
        volume_id = self.get_volume(volume_name)['id']
        print(f"v:{volume_id}, i:{instance_id}")
        return self._post(f'volume/{volume_id}/detach',
                          instanceId=instance_id,
                          )
