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
from AccessControl.interfaces import IRoleManager

from plone.app.discussion.browser.comments import CommentsViewlet 

# for debug purpose => log(...)
from Products.CMFPlone.utils import log

from ageliaco.tracker import _

import datetime

from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary
from zope.lifecycleevent.interfaces import IObjectCreatedEvent
from zope.app.container.interfaces import IObjectAddedEvent
from Products.CMFCore.utils import getToolByName

from plone.formwidget.autocomplete import AutocompleteMultiFieldWidget
from zope.interface import invariant, Invalid

from Acquisition import aq_inner, aq_parent
from zope.component import getUtility
from Products.CMFCore.interfaces import ISiteRoot

from DateTime import DateTime
from plone.indexer import indexer


class TwiceSameSupevisor(Invalid):
    __doc__ = _(u"Choisir un autre superviseur secondaire ou primaire!")


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
        parent = context.aq_inner.aq_parent
        log("context : " + context.__name__ + " parent : " + parent.__name__)
        users_roles = context.get_local_roles()
        users_with_the_role = [x[0] for x in users_roles if self.role_name in x[1]]
        while parent.Type() == "Tracker":
            parent_users_roles = parent.get_local_roles()
            parent_users_with_the_role = [x[0] for x in parent_users_roles if self.role_name in x[1]]
            users_with_the_role += parent_users_with_the_role
            parent = parent.aq_parent
        
        terms = []
        terms.append(SimpleVocabulary.createTerm('', str(''), ''))
        if users_with_the_role is not None:
            for member_id in users_with_the_role:
                log( member_id)
                user = acl_users.getUserById(member_id)
                if user is not None:
                    member_name = user.getProperty('fullname') or member_id
                    terms.append(SimpleVocabulary.createTerm(member_id, str(member_id), member_name))
            
        return SimpleVocabulary(terms)    



        

class IIssue(form.Schema):
    """
    Issue
    """
    
    # -*- Your Zope schema definitions here ... -*-
    responsible = schema.Choice(
            title=_(u"Responsable"),
            description=_(u"Personne qui supervise cette tâche"),
            source=getUserWithRole('Reviewer'),
            required=False,
        )


    content = RichText(
            title=_(u"Présentation"),
            description=_(u"Description de la tâche"),
            required=True,
        )    

    deadline = schema.Datetime(
            title=_(u"Deadline"),
            required=False,
        )



class AddForm(dexterity.AddForm):
    grok.name('issue')        

@form.default_value(field=IIssue['deadline'])
def startDefaultValue(data):
    # To get hold of the folder, do: context = data.context
    year = datetime.timedelta(days=365)
    return datetime.datetime.today() + year


@grok.subscribe(IIssue, IObjectAddedEvent)
def setReviewer(issue, event):
    log( "=== Default Reviewer Role Attribution in Issue ===")
    acl_users = getToolByName(issue, 'acl_users')
    mail_host = getToolByName(issue, 'MailHost')
    portal_url = getToolByName(issue, 'portal_url')
    
    parent = issue.aq_inner.aq_parent
    log( parent.__name__ + "parent local roles : " +str(parent.get_local_roles())
            + "\naq_parent'parent local roles : " + str(parent.aq_parent.get_local_roles()))
    
    users_with_the_role = []
    if parent.Type() == "Tracker":
        log( "Testing parent's reviewers")
        users_roles = parent.get_local_roles()
        log("users roles : " + str( users_roles))
        users_with_the_role = [x[0] for x in users_roles if 'Reviewer' in x[1]]
        for member in users_with_the_role:
            log("member : " + member)

    #Add local roles to a group
    if IRoleManager.providedBy(issue):
        for member in users_with_the_role:
            log( "adding roles (Reviewer) to " + member )
            issue.manage_addLocalRoles(member, ['Reviewer'])

    return


@indexer(IIssue)
def deadlineIndexer(obj):
    #if obj.end is None:
    #    return None
    return DateTime(obj.deadline.isoformat())
grok.global_adapter(deadlineIndexer, name="deadline")


####
# the idea is to provide a way to manage expiring dates to workflow states
# so an issue could have start and end dates to its "opened" state
# and when it expires a transition (close) is trigered and eventually its script also
#
# from http://lists.plone.org/pipermail/plone-setup/2006-February/006386.html
####
# from DateTime import DateTime
# import time
# 
# def applyTransition(self, transition, time_offset):
#      pc = self.portal_catalog
#      pw = self.portal_workflow
# 
#      t0 = DateTime(time.time() - time_offset * 3600)
# 
#      pending = 0
#      promoted = 0
# 
#      #
#      # Grab all of the offers that are only visible to premium members
#      #
# 
#      for obrain in pc.queryCatalog({'portal_type':"OfferFolder", 'review_state':"respondable_premium"}):
#          o = obrain.getObject()
#          last_transition = o.workflow_history['offer_folder_workflow'][-1]
#          t1 = last_transition.get('time')
# 
#          pending += 1
#          #
#          # Check to see if this offer has passed the blackout period
#          #
#          pending_objs = {}
#          if t1 < t0:
#              promoted += 1
#              #
#              # TODO: currently it silently ignores objects who's transition does not exist
#              #
#              for t in pw.getTransitionsFor(o):
#                  if t['id'] == transition:
#                     pw.doActionFor(o, transition)
# 
#          pending_objs[pending] = o.absolute_url()

# start and end date suppressed, because this role could be played by history
# 
#     start = schema.Datetime(
#             title=_(u"Start date"),
#             required=False,
#         )
# 
#     end = schema.Datetime(
#             title=_(u"End date"),
#             required=False,
#         )
        


# @form.default_value(field=IIssue['start'])
# def startDefaultValue(data):
#     # To get hold of the folder, do: context = data.context
#     return datetime.datetime.today() 
# 
# 
# @form.default_value(field=IIssue['end'])
# def endDefaultValue(data):
#     # To get hold of the folder, do: context = data.context
#     return datetime.datetime.today() + datetime.timedelta(10)
    
