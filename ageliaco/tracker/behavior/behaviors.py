"""Behaviours to assign contributors.

Includes a form field and a behaviour adapter that stores the data in the
standard Subject field.
"""

from rwproperty import getproperty, setproperty

from zope.interface import implements, alsoProvides
from zope.component import adapts

from plone.directives import form
from zope import schema

from Products.CMFCore.interfaces import IDublinCore

from ageliaco.tracker import _

from plone.formwidget.autocomplete import AutocompleteMultiFieldWidget

class IContributors(form.Schema):
    """Add contributors to content
    """
    
    form.widget(contributor=AutocompleteMultiFieldWidget)
    contributor = schema.List(
            title=_(u"Contributeurs"),
            default=[],
            value_type=schema.Choice(vocabulary=u"plone.principalsource.Users",),            
            required=False,
        )

alsoProvides(IContributors, form.IFormFieldProvider)

class Contributors(object):
    """Store contributors in the Dublin Core metadata contributors field. This makes
    contributors easy to search for.
    """
    implements(IContributors)
    adapts(IDublinCore)

    def __init__(self, context):
        self.context = context
    
    @getproperty
    def contributors(self):
        return set(self.context.contributors())
    @setproperty
    def contributors(self, value):
        if value is None:
            value = ()
        self.context.setContributors(tuple(value))