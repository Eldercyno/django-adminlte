import math

from django.contrib.auth.models import AnonymousUser

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

from django.views.generic import View
from django.shortcuts import redirect, render
from functools import wraps


class AdminMenu(object):

    def __init__(self, name, icon_classes='fa-circle-o', description=None, parent_menu=None, sort=0):
        self.description = description
        self.icon_classes = icon_classes
        self.view_name = None
        self.name = name
        self.sub_menus = []
        self.extra_view_names = []
        self.parent_menu = parent_menu
        self.sub_menus = []
        self.sort = sort

    def active(self, view_name):

        if view_name == self.view_name:
            return True

        return False


class AdminLTEBaseView(View):
    template_name = 'adminlte/index.html'

    # menu = AdminMenu(name="Dashboard", description='控制面板页面', icon_classes='fa-dashboard')

    def dispatch(self, request, *args, **kwargs):
        # Try to dispatch to the right method; if a method doesn't exist,
        # defer to the error handler. Also defer to the error handler if the
        # request method isn't on the approved list.

        if getattr(self, 'login_required', True):
            if not request.user.id or not request.user.is_staff:
                return redirect('adminlte.login')

        if request.method.lower() in self.http_method_names:
            handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
        else:
            handler = self.http_method_not_allowed
        return handler(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

    @classmethod
    def menus(cls):
        menus = []
        for clzss in cls.__subclasses__():
            if hasattr(clzss, 'menu'):
                menu = clzss.menu
                menu.view_name = clzss._view_name()
                menus.append(menu)

        last_menus = []
        for menu in menus:
            if not menu.parent_menu:
                last_menus.append(menu)
            else:
                parent_menu = menu.parent_menu
                if menu not in parent_menu.sub_menus:
                    parent_menu.sub_menus.append(menu)
                if parent_menu not in last_menus:
                    last_menus.append(parent_menu)

        return last_menus.sort(key=lambda menu: menu.sort, reverse=True)

    @classmethod
    def _regex_name(cls):
        char_list = []

        name = cls.__name__.replace('View', '')
        for index, char in enumerate(name):
            if char.isupper():
                if index != 0:
                    char_list.append('/')
                char_list.append(char.lower())
            else:
                char_list.append(char)

        return r'^%s$' % ''.join(char_list)

    @classmethod
    def _view_name(cls):
        char_list = []

        name = cls.__name__.replace('View', '')
        for index, char in enumerate(name):
            if char.isupper():
                char_list.append('.')
                char_list.append(char.lower())
            else:
                char_list.append(char)

        return 'adminlte' + ''.join(char_list)

    @classmethod
    def urlpatterns(cls):
        from django.conf.urls import url

        urlpatterns = []
        for clzss in cls.__subclasses__():
            regex_name = clzss._regex_name() if callable(clzss._regex_name) else clzss._regex_name
            if regex_name == r'^index$':
                urlpatterns.append(url(r'^$', clzss.as_view()))
            urlpatterns.append(url(regex_name, clzss.as_view(), name=clzss._view_name()))

        return urlpatterns


class RootMenu(object):

    def __init__(self, current_view_name, init_menus):
        self.current_view_name = current_view_name
        self.current_menu = None
        self.parent_menu = None
        self.menus = []

        for menu in init_menus:
            self.add_menu(menu)

    def add_menu(self, menu):
        view_name = self.current_view_name
        if menu.active(view_name):
            self.current_menu = menu
        elif menu.sub_menus:
            for sub_menu in menu.sub_menus:
                if sub_menu.active(view_name):
                    self.current_menu = sub_menu
                    self.parent_menu = menu
                    break

        self.menus.append(menu)
        return self


class Pager(object):

    def __init__(self, query, page, size, params=None):
        self.count = query.count()

        start = (page - 1) * size
        end = start + size
        self.items = query[start: end]
        self.page = page
        self.size = size
        self.params = params

    @property
    def has_next(self):
        return self.count > self.page * self.size

    @property
    def has_next_two(self):
        return self.count > (self.page + 1) * self.size

    @property
    def last_page(self):
        return math.ceil(self.count / self.size)

    @classmethod
    def from_request(cls, query, request):
        page = int(request.GET.get('page', 1))
        size = int(request.GET.get('size', 20))
        params = {k: v[0] for k, v in dict(request.GET).items()}

        if 'page' in params:
            params.pop('page')

        if 'size' in params:
            params.pop('size')

        params.update(size=size)
        return Pager(query, page, size, params)

    @property
    def url_params(self):
        return urlencode(self.params)


def admin_config(request):

    if isinstance(request.user, AnonymousUser):
        name = '游客'
        date_joined = None
    else:
        name = "{first_name} {last_name}".format(first_name=request.user.first_name, last_name=request.user.last_name)
        date_joined = request.user.date_joined

    return {
        "ROOT_MENU": RootMenu(current_view_name=request.resolver_match.view_name, init_menus=AdminLTEBaseView.menus()),
        "current_user": {
            "nickname": name,
            "avatar_url": "/static/adminLTE/img/avatar5.png",
            "date_joined": date_joined,
        },
    }


def admin_only(api_func):
    @wraps(api_func)
    def _warp(request, *args, **kwargs):
        if not request.user.id or not request.user.is_staff:
            return redirect('adminlte.login')

        return api_func(request, *args, **kwargs)
    return _warp