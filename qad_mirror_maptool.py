# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QAD Quantum Aided Design plugin

 classe per gestire il map tool in ambito del comando mirror
 
                              -------------------
        begin                : 2013-12-11
        copyright            : iiiii
        email                : hhhhh
        developers           : bbbbb aaaaa ggggg
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""


from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *
import math


import qad_utils
from qad_snapper import *
from qad_snappointsdisplaymanager import *
from qad_variables import *
from qad_getpoint import *
from qad_dim import *
from qad_rubberband import QadRubberBand


#===============================================================================
# Qad_copy_maptool_ModeEnum class.
#===============================================================================
class Qad_mirror_maptool_ModeEnum():
   # noto niente si richiede il primo punto della linea speculare
   NONE_KNOWN_ASK_FOR_FIRST_PT = 1     
   # noto il primo punto si richiede il secondo punto della linea speculare
   FIRST_PT_KNOWN_ASK_FOR_SECOND_PT = 2     

#===============================================================================
# Qad_mirror_maptool class
#===============================================================================
class Qad_mirror_maptool(QadGetPoint):
    
   def __init__(self, plugIn):
      QadGetPoint.__init__(self, plugIn)
                        
      self.firstMirrorPt = None
      self.entitySet = QadEntitySet()
      self.__rubberBand = QadRubberBand(self.canvas)

   def hidePointMapToolMarkers(self):
      QadGetPoint.hidePointMapToolMarkers(self)
      self.__rubberBand.hide()

   def showPointMapToolMarkers(self):
      QadGetPoint.showPointMapToolMarkers(self)
      self.__rubberBand.show()
                             
   def clear(self):
      QadGetPoint.clear(self)
      self.__rubberBand.reset()
      self.mode = None    
   

   #============================================================================
   # mirror
   #============================================================================
   def mirror(self, f, pt1, pt2, layerEntitySet, entitySet):
      # verifico se la feature appartiene ad una quotatura
      dimEntity = self.plugIn.dimStyles.getDimEntity(layerEntitySet.layer, f.id())
      
      if dimEntity is None:
         # specchio la feature e la rimuovo da entitySet (é la prima)
         f.setGeometry(qad_utils.mirrorQgsGeometry(f.geometry(), pt1, pt2))
         self.__rubberBand.addGeometry(f.geometry(), layerEntitySet.layer)
         del layerEntitySet.featureIds[0]
      else:
         # specchio la quota e la rimuovo da entitySet
         dimEntitySet = dimEntity.getEntitySet()         
         dimEntity.mirror(self.plugIn, pt1, qad_utils.getAngleBy2Pts(pt1, pt2))
         self.__rubberBand.addGeometry(dimEntity.textualFeature.geometry(), dimEntity.getTextualLayer())
         self.__rubberBand.addGeometries(dimEntity.getLinearGeometryCollection(), dimEntity.getLinearLayer())
         self.__rubberBand.addGeometries(dimEntity.getSymbolGeometryCollection(), dimEntity.getSymbolLayer())
         entitySet.subtract(dimEntitySet)
   
   
   def setMirroredGeometries(self, newPt):
      self.__rubberBand.reset()

      # copio entitySet
      entitySet = QadEntitySet(self.entitySet)
                
      for layerEntitySet in entitySet.layerEntitySetList:
         layer = layerEntitySet.layer

         transformedFirstMirrorPt = self.canvas.mapRenderer().mapToLayerCoordinates(layer, self.firstMirrorPt)
         transformedNewPtMirrorPt = self.canvas.mapRenderer().mapToLayerCoordinates(layer, newPt)

         while len(layerEntitySet.featureIds) > 0:
            featureId = layerEntitySet.featureIds[0]
            f = layerEntitySet.getFeature(featureId)
            self.mirror(f, transformedFirstMirrorPt, transformedNewPtMirrorPt, layerEntitySet, entitySet)
                     
      
   def canvasMoveEvent(self, event):
      QadGetPoint.canvasMoveEvent(self, event)
                     
      # noto il primo punto si richiede il secondo punto della linea speculare
      if self.mode == Qad_mirror_maptool_ModeEnum.FIRST_PT_KNOWN_ASK_FOR_SECOND_PT:
         self.setMirroredGeometries(self.tmpPoint)                           
         
    
   def activate(self):
      QadGetPoint.activate(self)  
      self.__rubberBand.show()          

   def deactivate(self):
      try: # necessario perché se si chiude QGIS parte questo evento nonostante non ci sia più l'oggetto maptool !
         QadGetPoint.deactivate(self)
         self.__rubberBand.hide()
      except:
         pass

   def setMode(self, mode):
      self.mode = mode
      # noto niente si richiede il primo punto della linea speculare
      if self.mode == Qad_mirror_maptool_ModeEnum.NONE_KNOWN_ASK_FOR_FIRST_PT:
         self.setDrawMode(QadGetPointDrawModeEnum.NONE)
      # noto il primo punto si richiede il secondo punto della linea speculare
      elif self.mode == Qad_mirror_maptool_ModeEnum.FIRST_PT_KNOWN_ASK_FOR_SECOND_PT:
         self.setDrawMode(QadGetPointDrawModeEnum.ELASTIC_LINE)
         self.setStartPoint(self.firstMirrorPt)