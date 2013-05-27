# -*- coding: UTF-8 -*-
from five import grok
from zope import schema
from plone.namedfile import field as namedfile
from z3c.relationfield.schema import RelationChoice, RelationList
from plone.formwidget.contenttree import ObjPathSourceBinder

from plone.directives import form, dexterity
from plone.app.textfield import RichText
from plone.app.z3cform.wysiwyg import WysiwygFieldWidget
from zope.lifecycleevent.interfaces import IObjectModifiedEvent
from zope.schema.fieldproperty import FieldProperty
from zope.schema.interfaces import IVocabularyFactory
from AccessControl.interfaces import IRoleManager

# for debug purpose => log(...)
from Products.CMFPlone.utils import log

from ageliaco.tracker import _

from ageliaco.tracker.content.issue import IIssue
import datetime

from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary
from zope.lifecycleevent.interfaces import IObjectCreatedEvent
from zope.app.container.interfaces import IObjectAddedEvent
from Products.CMFCore.utils import getToolByName

from plone.formwidget.autocomplete import AutocompleteMultiFieldWidget
from plone.formwidget.contenttree import MultiContentTreeFieldWidget
from zope.interface import invariant, Invalid

from Acquisition import aq_inner, aq_parent
from zope.component import getUtility
from Products.CMFCore.interfaces import ISiteRoot


class GroupMembers(object):
    """Context source binder to provide a vocabulary of users in a given
    group.
    """
    
    grok.implements(IContextSourceBinder)
    
    def __init__(self, group_name):
        self.group_name = group_name
    
    def __call__(self, context):
        acl_users = getToolByName(context, 'acl_users')
        group = acl_users.getGroupById(self.group_name)
        terms = []
        terms.append(SimpleVocabulary.createTerm('', str(''), ''))
        if group is not None:
            for member_id in group.getMemberIds():
                user = acl_users.getUserById(member_id)
                if user is not None:
                    member_name = user.getProperty('fullname') or member_id
                    terms.append(SimpleVocabulary.createTerm(member_id, str(member_id), member_name))
            
        return SimpleVocabulary(terms)    

class getUserWithRole(object):
    """Context source binder to provide a vocabulary of users in a given
    group.
    """
    
    grok.implements(IContextSourceBinder)
    
    def __init__(self, role_name):
        self.role_name = role_name
    
    def __call__(self, context):
        acl_users = getToolByName(context, 'acl_users')
        users_roles = context.get_local_roles()
        users_with_the_role = [x[0] for x in users_roles if role_name in x[1]]
        
        terms = []
        terms.append(SimpleVocabulary.createTerm('', str(''), ''))
        if users_with_the_role is not None:
            for member_id in users_with_the_role:
                user = acl_users.getUserById(member_id)
                if user is not None:
                    member_name = user.getProperty('fullname') or member_id
                    terms.append(SimpleVocabulary.createTerm(member_id, str(member_id), member_name))
            
        return SimpleVocabulary(terms)    

class KeywordsVocabulary(object):
    """Vocabulary factory listing all catalog keywords from the "Subject" index
  
        >>> from plone.app.vocabularies.tests.base import DummyCatalog
        >>> from plone.app.vocabularies.tests.base import create_context
        >>> from plone.app.vocabularies.tests.base import DummyContent
        >>> from plone.app.vocabularies.tests.base import Request
        >>> from Products.PluginIndexes.KeywordIndex.KeywordIndex import KeywordIndex
  
        >>> context = create_context()
  
        >>> rids = ('/1234', '/2345', '/dummy/1234')
        >>> tool = DummyCatalog(rids)
        >>> context.portal_catalog = tool
        >>> index = KeywordIndex('Subject')
        >>> done = index._index_object(1,DummyContent('ob1', ['foo', 'bar', 'baz']), attr='Subject')
        >>> done = index._index_object(2,DummyContent('ob2', ['blee', 'bar']), attr='Subject')
        >>> tool.indexes['Subject'] = index
        >>> vocab = KeywordsVocabulary()
        >>> result = vocab(context)
        >>> result.by_token.keys()
        ['blee', 'baz', 'foo', 'bar']
    """
    grok.implements(IVocabularyFactory)
    def __call__(self, context):
        self.context = context
        self.catalog = getToolByName(context, "portal_catalog")
        if self.catalog is None:
            return SimpleVocabulary([])
        index = self.catalog._catalog.getIndex('Subject')
        items = [SimpleTerm(i, i, i) for i in index._index]
        return SimpleVocabulary(items)

grok.global_utility(KeywordsVocabulary, name=u"ageliaco.rd.tracker.Subjects")


        

class ITracker(form.Schema):
    """
    ITracker
    """
    
    # -*- Your Zope schema definitions here ... -*-
    content = RichText(
            title=_(u"Content"),
            required=True,
        )    

@grok.subscribe(ITracker, IObjectAddedEvent)
def setReviewer(tracker, event):
    log( "=== Default Reviewer Role Attribution ===")
    acl_users = getToolByName(tracker, 'acl_users')
    mail_host = getToolByName(tracker, 'MailHost')
    portal_url = getToolByName(tracker, 'portal_url')
    
    parent = tracker.aq_inner.aq_parent
    log( parent.__name__ + "parent local roles : " +str(parent.get_local_roles())
            + "\naq_parent'parent local roles : " + str(parent.aq_parent.get_local_roles()) 
            + "\ntracker's aq_parent local roles : " + str(tracker.aq_parent.get_local_roles()))
    
    users_with_the_role = []
    if parent.Type() == "Tracker":
        log( "Testing parent's reviewers")
        users_roles = parent.get_local_roles()
        print users_roles
        users_with_the_role = [x[0] for x in users_roles if 'Reviewer' in x[1]]
        for member in users_with_the_role:
            print member

    #Add local roles to a group
    if IRoleManager.providedBy(tracker):
        for member in users_with_the_role:
            log( "adding roles (Reviewer) to " + member)
            tracker.manage_addLocalRoles(member, ['Reviewer'])

    return

class View(grok.View):
    grok.context(ITracker)
    grok.require('zope2.View')
    
    def subtrackers(self):
        """Return a catalog search result of issues to show
        """
        
        context = aq_inner(self.context)
        catalog = getToolByName(context, 'portal_catalog')
        log( "context's physical path : " + '/'.join(context.getPhysicalPath()))
        log( "all subtrackers")
        return catalog(object_provides=[ITracker.__identifier__],
                       path={'query': '/'.join(context.getPhysicalPath()), 'depth': 1},
                       sort_on='sortable_title')

    def subTrackerIssues(self, object, wf_state='all'):
        """Return a catalog search result of issues to show
        """
        
        context = aq_inner(self.context)
        catalog = getToolByName(self.context, 'portal_catalog')
        log( 'subtracker : ' + object.getPath())
        log( wf_state + " state chosen")
        if wf_state == 'all':
            log( "all issues")
            return catalog(object_provides=[IIssue.__identifier__,ITracker.__identifier__],
                           path={'query': object.getPath(), 'depth': 1},
                           sort_on="modified", sort_order="reverse")        
        return catalog(object_provides=[IIssue.__identifier__,ITracker.__identifier__],
                       review_state=wf_state,
                       path={'query': object.getPath(), 'depth': 1},
                       sort_on='sortable_title')
    
    def issues(self, wf_state='all'):
        """Return a catalog search result of issues to show
        """
        
        context = aq_inner(self.context)
        log("context : " + str(context))
        log("self.context : " + str(self.context))
        catalog = getToolByName(context, 'portal_catalog')
        log( "context's physical path : " + '/'.join(context.getPhysicalPath()))
        log(wf_state + " state chosen")
        if wf_state == 'all':
            log( "all issues")
            return catalog(object_provides=[IIssue.__identifier__],
                           path={'query': '/'.join(context.getPhysicalPath()), 'depth': 1},
                           sort_on="modified", sort_order="reverse")        
        aq = catalog(object_provides=[IIssue.__identifier__],
                       review_state=wf_state,
                       path={'query': '/'.join(context.getPhysicalPath()), 'depth': 1},
                       sort_on='deadline')
        #return catalog.evalAdvancedQuery(aq, (('deadline', 'asc'), ('effective', 'asc')))
        return aq