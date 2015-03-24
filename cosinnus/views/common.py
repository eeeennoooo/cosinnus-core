# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.urlresolvers import reverse_lazy
from django.views.generic import RedirectView
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _

from cosinnus.conf import settings
from django.views.generic.base import TemplateView
from django.shortcuts import render_to_response

from cosinnus.utils.context_processors import cosinnus as cosinnus_context

class IndexView(RedirectView):
    url = reverse_lazy('cosinnus:group-list')

index = IndexView.as_view()

"""
class PermissionDeniedView(TemplateView):
    template_name = '403.html'
    
view_403 = PermissionDeniedView.as_view()

class NotFoundView(TemplateView):
    template_name = '404.html'
    
view_404 = NotFoundView.as_view()
"""

def _get_bare_cosinnus_context(request):
    context = {
        'request': request,
        'user': request.user,
    }
    context.update(cosinnus_context(request))
    return context


def view_403(request):
    return render_to_response('cosinnus/common/403.html', _get_bare_cosinnus_context(request))

def view_404(request):
    return render_to_response('cosinnus/common/404.html', _get_bare_cosinnus_context(request))

def view_500(request):
    return render_to_response('cosinnus/common/500.html')


class SwitchLanguageView(RedirectView):
    
    def get(self, request, *args, **kwargs):
        language = kwargs.pop('language', None)
        if not language or language not in dict(settings.LANGUAGES).keys():
            messages.error(request, _('The language "%s" is not supported' % language))
            
        request.session['django_language'] = language
        #messages.success(request, _('Language was switched successfully.'))
        
        return super(SwitchLanguageView, self).get(request, *args, **kwargs)
        
    def get_redirect_url(self, **kwargs):
        return self.request.GET.get('next', self.request.META.get('HTTP_REFERER', '/'))
        

switch_language = SwitchLanguageView.as_view()
