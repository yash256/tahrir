
import hashlib
import transaction

from mako.template import Template as t
from pyramid.view import (
    view_config,
    forbidden_view_config,
)

from pyramid.httpexceptions import HTTPFound

from pyramid.security import (
    authenticated_userid,
    remember,
    forget,
)

import model as m
import widgets


# TODO -- really wield tw2.sqla here
@view_config(route_name='admin', renderer='admin.mak')
def admin(request):
    logged_in = authenticated_userid(request)

    if logged_in != request.registry.settings['tahrir.admin']:
        return HTTPFound(location='/')

    cls = None
    if any([k.startswith('issuer') for k in request.params]):
        keys = ['origin', 'name', 'org', 'contact']
        cls = m.Issuer

    if any([k.startswith('badge') for k in request.params]):
        keys = ['name', 'image', 'description', 'criteria', 'issuer_id']
        cls = m.Badge

    if any([k.startswith('assertion') for k in request.params]):
        keys = ['badge_id', 'person_id']
        cls = m.Assertion

    if any([k.startswith('person') for k in request.params]):
        keys = ['email']
        cls = m.Person

    if cls:
        with transaction.manager:
            name_lookup = {
                m.Issuer: "issuerform",
                m.Badge: "badgeform",
                m.Assertion: "assertionform",
                m.Person: "personform",
            }
            mod = lambda k: name_lookup[cls] + ":" + k
            obj = cls(**dict((k, request.params[mod(k)]) for k in keys))

            # NOTE -- crashing happens right here for Assertion.
            # TODO -- instead, I should use the tw2.sqla backend code to get all
            # the relational stuff right for me.
            if cls == m.Assertion:
                obj.recipient = hashlib.sha256(
                    obj.person.email + obj.salt).hexdigest()

            m.DBSession.add(obj)

        return HTTPFound(location='/')

    return dict(
        issuer_form = widgets.IssuerForm,
        badge_form = widgets.BadgeForm,
        assertion_form = widgets.AssertionForm,
        person_form = widgets.PersonForm,
    )


@view_config(route_name='home', renderer='index.mak')
def index(request):
    logged_in = authenticated_userid(request)
    is_awarded = lambda a: logged_in and a.person.email == logged_in
    awarded_assertions = filter(is_awarded, m.Assertion.query.all())
    return dict(
        issuers=m.Issuer.query.all(),
        awarded_assertions=awarded_assertions,
        logged_in=logged_in,
        title=request.registry.settings['tahrir.title'],
    )


@view_config(context=m.Assertion, renderer='json')
def json(context, request):
    return context.__json__()


@view_config(route_name='login', renderer='templates/login.pt')
@forbidden_view_config(renderer='templates/login.pt')
def login(request):
    login_url = request.resource_url(request.context, 'login')
    referrer = request.url
    if referrer == login_url:
        referrer = '/' # never use the login form itself as came_from
    came_from = request.params.get('came_from', referrer)
    message = ''
    email = ''
    if 'form.submitted' in request.params:
        email = request.params['email']
        if m.Person.query.filter_by(email=email).count() == 0:
            new_user = m.Person(email=email)
            m.DBSession.add(new_user)

        # NOTE -- there is no way to fail login here :D
        # TODO -- validate the email address
        if True:
            headers = remember(request, email)
            return HTTPFound(location = came_from,
                             headers = headers)
        message = 'Failed login'

    return dict(
        message = message,
        url = request.application_url + '/login',
        came_from = came_from,
        email = email,
        )


@view_config(route_name='logout')
def logout(request):
    headers = forget(request)
    return HTTPFound(location = request.resource_url(request.context),
                     headers = headers)

