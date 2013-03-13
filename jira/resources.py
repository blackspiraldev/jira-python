"""
This module implements the Resource classes that translate JSON from JIRA REST resources
into usable objects.
"""

import re
from jira.exceptions import raise_on_error
import json


class Resource(object):
    """
    Models a URL-addressable resource in the JIRA REST API.

    All Resource objects provide the following:
    ``find()`` -- get a resource from the server and load it into the current object
    (though clients should use the methods in the JIRA class instead of this method directly)
    ``update()`` -- changes the value of this resource on the server and returns a new resource object for it
    ``delete()`` -- deletes this resource from the server
    ``self`` -- the URL of this resource on the server
    ``raw`` -- dict of properties parsed out of the JSON response from the server

    Subclasses will implement ``update()`` and ``delete()`` as appropriate for the specific resource.

    All Resources have a resource path of the form:

    * ``issue``
    * ``project/{0}``
    * ``issue/{0}/votes``
    * ``issue/{0}/comment/{1}``

    where the bracketed numerals are placeholders for ID values that are filled in from the
    ``ids`` parameter to ``find()``.
    """

    def __init__(self, resource, options, session):
        self._resource = resource
        self._options = options
        self._session = session

        # explicitly define as None so we know when a resource has actually been loaded
        self.raw = None
        self.self = None

    def find(self, ids=None, headers=None, params=None):
        if ids is None:
            ids = ()

        if isinstance(ids, basestring):
            ids = (ids,)

        if headers is None:
            headers = {}

        if params is None:
            params = {}

        url = self._url(ids)
        headers = self._default_headers(headers)
        self._load(url, headers, params)

    def update(self, **kwargs):
        """
        Update this resource on the server. Keyword arguments are marshalled into a dict before being sent. If this
        resource doesn't support ``PUT``, a :py:exc:`.JIRAError` will be raised; subclasses that specialize this method
        will only raise errors in case of user error.
        """
        data = {}
        for arg in kwargs:
            data[arg] = kwargs[arg]

        r = self._session.put(self.self, data=json.dumps(data))
        raise_on_error(r)

        self._load(self.self)

    def delete(self, params=None):
        """
        Delete this resource from the server, passing the specified query parameters. If this resource doesn't support
        ``DELETE``, a :py:exc:`.JIRAError` will be raised; subclasses that specialize this method will only raise errors
        in case of user error.
        """
        r = self._session.delete(self.self, params=params)
        raise_on_error(r)

    def _load(self, url, headers=None, params=None):
        r = self._session.get(url, headers=headers, params=params)
        raise_on_error(r)

        self._parse_raw(json.loads(r.text))

    def _parse_raw(self, raw):
        self.raw = raw
        dict2resource(raw, self, self._options, self._session)

    def _url(self, ids):
        url = '{server}/rest/{rest_path}/{rest_api_version}/'.format(**self._options)
        url += self._resource.format(*ids)
        return url

    def _default_headers(self, user_headers):
        return dict(user_headers.items() + {'accept': 'application/json'}.items())


class Attachment(Resource):
    """An issue attachment."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'attachment/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class Component(Resource):
    """A project component."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'component/{0}', options, session)
        if raw:
            self._parse_raw(raw)

    def delete(self, moveIssuesTo=None):
        """
        Delete this component from the server.

        :param moveIssuesTo: the name of the component to which to move any issues this component is applied
        """
        params = {}
        if moveIssuesTo is not None:
            params['moveIssuesTo'] = moveIssuesTo

        super(Component, self).delete(params)


class CustomFieldOption(Resource):
    """An existing option for a custom issue field."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'customFieldOption/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class Dashboard(Resource):
    """A JIRA dashboard."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'dashboard/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class Filter(Resource):
    """An issue navigator filter."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'filter/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class Issue(Resource):
    """A JIRA issue."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'issue/{0}', options, session)
        if raw:
            self._parse_raw(raw)

    def update(self, fields=None, **fieldargs):
        """
        Update this issue on the server.

        Each keyword argument (other than the predefined ones) is treated as a field name and the argument's value
        is treated as the intended value for that field -- if the fields argument is used, all other keyword arguments
        will be ignored.

        JIRA projects may contain many different issue types. Some issue screens have different requirements for
        fields in an issue. This information is available through the :py:meth:`.JIRA.editmeta` method. Further examples
        are available here: https://developer.atlassian.com/display/JIRADEV/JIRA+REST+API+Example+-+Edit+issues

        :param fields: a dict containing field names and the values to use; if present, all other keyword arguments\
        will be ignored
        """
        data = {}
        if fields is not None:
            data['fields'] = fields
        else:
            fields_dict = {}
            for field in fieldargs:
                fields_dict[field] = fieldargs[field]
            data['fields'] = fields_dict

        super(Issue, self).update(**data)

    def delete(self, deleteSubtasks=False):
        """
        Delete this issue from the server.

        :param deleteSubtasks: if the issue has subtasks, this argument must be set to true for the call to succeed.
        """
        super(Issue, self).delete(params={'deleteSubtasks': deleteSubtasks})


class Comment(Resource):
    """An issue comment."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'issue/{0}/comment/{1}', options, session)
        if raw:
            self._parse_raw(raw)


class RemoteLink(Resource):
    """A link to a remote application from an issue."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'issue/{0}/remotelink/{1}', options, session)
        if raw:
            self._parse_raw(raw)

    def update(self, object, globalId=None, application=None, relationship=None):
        """
        Update a RemoteLink. 'object' is required and should be

        For definitions of the allowable fields for 'object' and the keyword arguments 'globalId', 'application' and
        'relationship', see https://developer.atlassian.com/display/JIRADEV/JIRA+REST+API+for+Remote+Issue+Links.

        :param object: the link details to add (see the above link for details)
        :param globalId: unique ID for the link (see the above link for details)
        :param application: application information for the link (see the above link for details)
        :param relationship: relationship description for the link (see the above link for details)
        """
        data = {
            'object': object
        }
        if globalId is not None:
            data['globalId'] = globalId
        if application is not None:
            data['application'] = application
        if relationship is not None:
            data['relationship'] = relationship

        super(RemoteLink, self).update(**data)


class Votes(Resource):
    """Vote information on an issue."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'issue/{0}/votes', options, session)
        if raw:
            self._parse_raw(raw)


class Watchers(Resource):
    """Watcher information on an issue."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'issue/{0}/watchers', options, session)
        if raw:
            self._parse_raw(raw)

    def delete(self, username):
        """
        Remove the specified user from the watchers list.
        """
        super(Watchers, self).delete(params={'username': username})


class Worklog(Resource):
    """Worklog on an issue."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'issue/{0}/worklog/{1}', options, session)
        if raw:
            self._parse_raw(raw)

    def delete(self, adjustEstimate=None, newEstimate=None, increaseBy=None):
        """
        Delete this worklog entry from its associated issue.

        :param adjustEstimate: one of ``new``, ``leave``, ``manual`` or ``auto``. ``auto`` is the default and adjusts\
        the estimate automatically. ``leave`` leaves the estimate unchanged by this deletion.
        :param newEstimate: combined with ``adjustEstimate=new``, set the estimate to this value
        :param increaseBy: combined with ``adjustEstimate=manual``, increase the remaining estimate by this amount
        """
        params = {}
        if adjustEstimate is not None:
            params['adjustEstimate'] = adjustEstimate
        if newEstimate is not None:
            params['newEstimate'] = newEstimate
        if increaseBy is not None:
            params['increaseBy'] = increaseBy

        super(Worklog, self).delete(params)


class IssueLink(Resource):
    """Link between two issues."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'issueLink/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class IssueLinkType(Resource):
    """Type of link between two issues."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'issueLinkType/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class IssueType(Resource):
    """Type of an issue."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'issuetype/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class Priority(Resource):
    """Priority that can be set on an issue."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'priority/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class Project(Resource):
    """A JIRA project."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'project/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class Role(Resource):
    """A role inside a project."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'project/{0}/role/{1}', options, session)
        if raw:
            self._parse_raw(raw)

    def update(self, users=None, groups=None):
        """
        Add the specified users or groups to this project role. One of ``users`` or ``groups`` must be specified.

        :param users: a user or users to add to the role
        :type users: string, list or tuple
        :param groups: a group or groups to add to the role
        :type groups: string, list or tuple
        """
        if users is not None and isinstance(users, basestring):
            users = (users,)
        if groups is not None and isinstance(groups, basestring):
            groups = (groups,)

        data = {
            'id': self.id,
            'categorisedActors': {
                'atlassian-user-role-actor': users,
                'atlassian-group-role-actor': groups
            }
        }

        super(Role, self).update(**data)


class Resolution(Resource):
    """A resolution for an issue."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'resolution/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class SecurityLevel(Resource):
    """A security level for an issue or project."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'securitylevel/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class Status(Resource):
    """Status for an issue."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'status/{0}', options, session)
        if raw:
            self._parse_raw(raw)


class User(Resource):
    """A JIRA user."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'user?username={0}', options, session)
        if raw:
            self._parse_raw(raw)


class Version(Resource):
    """A version of a project."""

    def __init__(self, options, session, raw=None):
        Resource.__init__(self, 'version/{0}', options, session)
        if raw:
            self._parse_raw(raw)

    def delete(self, moveFixIssuesTo=None, moveAffectedIssuesTo=None):
        """
        Delete this project version from the server. If neither of the arguments are specified, the version is
        removed from all issues it is attached to.

        :param moveFixIssuesTo: in issues for which this version is a fix version, add this argument version to the fix\
        version list
        :param moveAffectedIssuesTo: in issues for which this version is an affected version, add this argument version\
        to the affected version list
        """
        params = {}
        if moveFixIssuesTo is not None:
            params['moveFixIssuesTo'] = moveFixIssuesTo
        if moveAffectedIssuesTo is not None:
            params['moveAffectedIssuesTo'] = moveAffectedIssuesTo

        super(Version, self).delete(params)


def dict2resource(raw, top=None, options=None, session=None):
    """
    Recursively walks a dict structure, transforming the properties into attributes
    on a new ``Resource`` object of the appropriate type (if a ``self`` link is present)
    or a ``PropertyHolder`` object (if no ``self`` link is present).
    """
    if top is None:
        top = type('PropertyHolder', (object,), raw)

    seqs = tuple, list, set, frozenset
    for i, j in raw.iteritems():
        if isinstance(j, dict):
            if 'self' in j:
                resource = cls_for_resource(j['self'])(options, session, j)
                setattr(top, i, resource)
            else:
                setattr(top, i, dict2resource(j, options=options, session=session))
        elif isinstance(j, seqs):
            seq_list = []
            for seq_elem in j:
                if isinstance(seq_elem, dict):
                    if 'self' in seq_elem:
                        resource = cls_for_resource(seq_elem['self'])(options, session, seq_elem)
                        seq_list.append(resource)
                    else:
                        seq_list.append(dict2resource(seq_elem, options=options, session=session))
                else:
                    seq_list.append(seq_elem)
            setattr(top, i, seq_list)
        else:
            setattr(top, i, j)
    return top

resource_class_map = {
    r'attachment/[^/]+$': Attachment,
    r'component/[^/]+$': Component,
    r'customFieldOption/[^/]+$': CustomFieldOption,
    r'dashboard/[^/]+$': Dashboard,
    r'filter/[^/]$': Filter,
    r'issue/[^/]+$': Issue,
    r'issue/[^/]+/comment/[^/]+$': Comment,
    r'issue/[^/]+/votes$': Votes,
    r'issue/[^/]+/watchers$': Watchers,
    r'issue/[^/]+/worklog/[^/]+$': Worklog,
    r'issueLink/[^/]+$': IssueLink,
    r'issueLinkType/[^/]+$': IssueLinkType,
    r'issuetype/[^/]+$': IssueType,
    r'priority/[^/]+$': Priority,
    r'project/[^/]+$': Project,
    r'project/[^/]+/role/[^/]+$': Role,
    r'resolution/[^/]+$': Resolution,
    r'securitylevel/[^/]+$': SecurityLevel,
    r'status/[^/]+$': Status,
    r'user\?username.+$': User,
    r'version/[^/]+$': Version,
}


def cls_for_resource(resource_literal):
    for resource in resource_class_map:
        if re.search(resource, resource_literal):
            return resource_class_map[resource]
    else:
        # generic Resource without specialized update/delete behavior
        return Resource
