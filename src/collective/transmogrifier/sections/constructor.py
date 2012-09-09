from ComputedAttribute import ComputedAttribute
from zope.interface import classProvides, implements
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.utils import defaultMatcher

from Acquisition import aq_base
from Products.CMFCore.utils import getToolByName

import logging
logger = logging.getLogger('collective.transmogrifier.constructor')

class ConstructorSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)
    
    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.ttool = getToolByName(self.context, 'portal_types')
        
        self.typekey = defaultMatcher(options, 'type-key', name, 'type', 
                                      ('portal_type', 'Type'))
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.required = bool(options.get('required'))
    
    def __iter__(self):
        for item in self.previous:
            keys = item.keys()
            typekey = self.typekey(*keys)[0]
            pathkey = self.pathkey(*keys)[0]
            
            if not (typekey and pathkey):             # not enough info
                yield item; continue
                        
            type_, path = item[typekey], item[pathkey]
            
            fti = self.ttool.getTypeInfo(type_)
            if fti is None:                           # not an existing type
                yield item; continue
            
            path = path.encode('ASCII')
            elems = path.strip('/').rsplit('/', 1)
            container, id = (len(elems) == 1 and ('', elems[0]) or elems)
            context = self.context.unrestrictedTraverse(container, None)
            if context is None:                       # container doesn't exist
                error = 'Container %s does not exist for item %s' % (container, path)
                if self.required:
                    raise KeyError(error)
                logger.warn(error)
                yield item; continue
            
            # in some instance, we have 'index_html' contents
            # giving us either:
            #   - computed attribute 
            #   - page templates
            # on new container objects when the content 
            # does not exist yet
            tobj = getattr(aq_base(context), id, None)
            if tobj is not None:
                orepr = repr(tobj).lower()
                if (('fspagetemplate' in orepr)
                    or ('computedattribute' in orepr)
                   ):
                    try:
                        tobj = self.context.unrestrictedTraverse(
                            path.strip('/')).aq_inner
                    except Exception, e:
                        tobj = None
            # also take care to filter out :
            # - Acquisition grabbed contents
            if tobj is not None:
                tpath = '/'.join(context.getPhysicalPath()+(id,))
                cpath = '/'.join(context.getPhysicalPath())+ '/'
                if ((not tpath.startswith(cpath))
                    or ('fspagetemplate' in orepr)
                    or ('computedattribute' in orepr)
                   ): 
                    tobj = None

            if  (tobj is not None 
                 and not isinstance(tobj, ComputedAttribute)
                ): # item exists

                yield item; continue
            

            obj = fti._constructInstance(context, id)

            
            # For CMF <= 2.1 (aka Plone 3)
            if hasattr(fti, '_finishConstruction'):
                obj = fti._finishConstruction(obj)
            
            if obj.getId() != id:
                item[pathkey] = '%s/%s' % (container, obj.getId())
            
            yield item
