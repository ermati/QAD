# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QAD Quantum Aided Design plugin

 comando TRIM per tagliare o estendere oggetti grafici
 
                              -------------------
        begin                : 2013-07-15
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


# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *


from qad_getpoint import *
from qad_textwindow import *
from qad_pline_cmd import QadPLINECommandClass
from qad_rectangle_cmd import QadRECTANGLECommandClass
from qad_generic_cmd import QadCommandClass
from qad_msg import QadMsg
import qad_utils
import qad_layer
from qad_ssget_cmd import QadSSGetClass


# Classe che gestisce il comando TRIM
class QadTRIMCommandClass(QadCommandClass):

   def instantiateNewCmd(self):
      """ istanzia un nuovo comando dello stesso tipo """
      return QadTRIMCommandClass(self.plugIn)
   
   def getName(self):
      return QadMsg.translate("Command_list", "TRIM")

   def getEnglishName(self):
      return "TRIM"

   def connectQAction(self, action):
      QObject.connect(action, SIGNAL("triggered()"), self.plugIn.runTRIMCommand)

   def getIcon(self):
      return QIcon(":/plugins/qad/icons/trim.png")

   def getNote(self):
      # impostare le note esplicative del comando
      return QadMsg.translate("Command_TRIM", "Trims (or extends) objects to meet the edges of other objects.")
   
   def __init__(self, plugIn):
      QadCommandClass.__init__(self, plugIn)
      self.SSGetClass = QadSSGetClass(plugIn)
      self.PLINECommand = None      
      self.RECTANGLECommand = None
      self.entitySet = QadEntitySet() # entità da tagliare o estendere
      self.limitEntitySet = QadEntitySet() # entità che fanno da limiti
      self.edgeMode = QadVariables.get(QadMsg.translate("Environment variables", "EDGEMODE"))
      self.defaultValue = None # usato per gestire il tasto dx del mouse
      self.nOperationsToUndo = 0

   def __del__(self):
      QadCommandClass.__del__(self)

   def getPointMapTool(self, drawMode = QadGetPointDrawModeEnum.NONE):
      if self.step == 3: # quando si é in fase di disegno linea
         return self.PLINECommand.getPointMapTool(drawMode)
      elif self.step == 4: # quando si é in fase di disegno rettangolo 
         return self.RECTANGLECommand.getPointMapTool(drawMode)      
      else:
         return QadCommandClass.getPointMapTool(self, drawMode)

   #============================================================================
   # trimFeatures
   #============================================================================
   def trimFeatures(self, geom, toExtend):
      LineTempLayer = None
      self.plugIn.beginEditCommand("Feature extended" if toExtend else "Feature trimmed", \
                                   self.entitySet.getLayerList())
      
      for layerEntitySet in self.entitySet.layerEntitySetList:
         layer = layerEntitySet.layer
         #layer.beginEditCommand("Feature extended") # test
         tolerance2ApproxCurve = qad_utils.distMapToLayerCoordinates(QadVariables.get(QadMsg.translate("Environment variables", "TOLERANCE2APPROXCURVE")), \
                                                                     self.plugIn.canvas,\
                                                                     layer)                              
                  
         g = QgsGeometry(geom)
         if self.plugIn.canvas.mapRenderer().destinationCrs() != layer.crs():         
            # Trasformo la geometria nel sistema di coordinate del layer
            coordTransform = QgsCoordinateTransform(self.plugIn.canvas.mapRenderer().destinationCrs(), \
                                                    layer.crs())          
            g.transform(coordTransform)
            
         for featureId in layerEntitySet.featureIds:
            f = qad_utils.getFeatureById(layer, featureId)
            
            if g.type() == QGis.Point:
               # ritorna una tupla (<The squared cartesian distance>,
               #                    <minDistPoint>
               #                    <afterVertex>
               #                    <leftOf>)
               dummy = qad_utils.closestSegmentWithContext(g.asPoint(), f.geometry())
               if dummy[1] is not None:
                  intPts = [dummy[1]]
            else:
               intPts = qad_utils.getIntersectionPoints(g, f.geometry())
               
            for intPt in intPts:               
               if toExtend:
                  newGeom = qad_utils.extendQgsGeometry(layer, f.geometry(), intPt, \
                                                        self.limitEntitySet, self.edgeMode, \
                                                        tolerance2ApproxCurve)
                  if newGeom is not None:
                     # aggiorno la feature con la geometria estesa
                     extendedFeature = QgsFeature(f)
                     extendedFeature.setGeometry(newGeom)
                     # plugIn, layer, feature, refresh, check_validity
                     if qad_layer.updateFeatureToLayer(self.plugIn, layer, extendedFeature, False, False) == False:
                        self.plugIn.destroyEditCommand()
                        return
               else: # trim
                  result = qad_utils.trimQgsGeometry(layer, f.geometry(), intPt, \
                                                    self.limitEntitySet, self.edgeMode, \
                                                    tolerance2ApproxCurve)                  
                  if result is not None:
                     line1 = result[0]
                     line2 = result[1]
                     atSubGeom = result[2]
                     if layer.geometryType() == QGis.Line:
                        updGeom = qad_utils.setSubGeom(f.geometry(), line1, atSubGeom)
                        if updGeom is None:
                           self.plugIn.destroyEditCommand()
                           return
                        trimmedFeature1 = QgsFeature(f)
                        trimmedFeature1.setGeometry(updGeom)
                        # plugIn, layer, feature, refresh, check_validity
                        if qad_layer.updateFeatureToLayer(self.plugIn, layer, trimmedFeature1, False, False) == False:
                           self.plugIn.destroyEditCommand()
                           return
                        if line2 is not None:
                           trimmedFeature2 = QgsFeature(f)      
                           trimmedFeature2.setGeometry(line2)
                           # plugIn, layer, feature, coordTransform, refresh, check_validity
                           if qad_layer.addFeatureToLayer(self.plugIn, layer, trimmedFeature2, None, False, False) == False:
                              self.plugIn.destroyEditCommand()
                              return                        
                     else:
                        # aggiungo le linee nei layer temporanei di QAD
                        if LineTempLayer is None:
                           LineTempLayer = qad_layer.createQADTempLayer(self.plugIn, QGis.Line)
                           self.plugIn.addLayerToLastEditCommand("Feature trimmed", LineTempLayer)
                        
                        lineGeoms = [line1]
                        if line2 is not None:
                           lineGeoms.append(line2)

                        # trasformo la geometria in quella dei layer temporanei
                        # plugIn, pointGeoms, lineGeoms, polygonGeoms, coord, refresh
                        if qad_layer.addGeometriesToQADTempLayers(self.plugIn, None, lineGeoms, None, layer.crs(), False) == False:
                           self.plugIn.destroyEditCommand()
                           return
                                                      
                        updGeom = qad_utils.delSubGeom(f.geometry(), atSubGeom)         
                        
                        if updGeom is None or updGeom.isGeosEmpty(): # da cancellare
                           # plugIn, layer, feature id, refresh
                           if qad_layer.deleteFeatureToLayer(self.plugIn, layer, f.id(), False) == False:
                              self.plugIn.destroyEditCommand()
                              return
                        else:
                           trimmedFeature1 = QgsFeature(f)
                           trimmedFeature1.setGeometry(updGeom)
                           # plugIn, layer, feature, refresh, check_validity
                           if qad_layer.updateFeatureToLayer(self.plugIn, layer, trimmedFeature1, False, False) == False:
                              self.plugIn.destroyEditCommand()
                              return

      self.plugIn.endEditCommand()
      self.nOperationsToUndo = self.nOperationsToUndo + 1
                                                      
      
   #============================================================================
   # waitForObjectSel
   #============================================================================
   def waitForObjectSel(self):      
      self.step = 2      
      # imposto il map tool
      self.getPointMapTool().setSelectionMode(QadGetPointSelectionModeEnum.ENTITY_SELECTION)
      # solo layer lineari editabili che non appartengano a quote
      layerList = []
      for layer in self.plugIn.canvas.layers():
         if layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QGis.Line and layer.isEditable():
            if len(self.plugIn.dimStyles.getDimListByLayer(layer)) == 0:
               layerList.append(layer)
            
      self.getPointMapTool().layersToCheck = layerList
      self.getPointMapTool().setDrawMode(QadGetPointDrawModeEnum.NONE)
      self.getPointMapTool().onlyEditableLayers = True
      
      keyWords = QadMsg.translate("Command_TRIM", "Fence") + "/" + \
                 QadMsg.translate("Command_TRIM", "Crossing") + "/" + \
                 QadMsg.translate("Command_TRIM", "Edge") + "/" + \
                 QadMsg.translate("Command_TRIM", "Undo")      
      prompt = QadMsg.translate("Command_TRIM", "Select the object to trim or shift-select to extend or [{0}]: ").format(keyWords)                        
      
      englishKeyWords = "Fence" + "/" + "Crossing" + "/" + "Edge" + "/" + "Undo"
      keyWords += "_" + englishKeyWords
      # si appresta ad attendere un punto o enter o una parola chiave         
      # msg, inputType, default, keyWords, nessun controllo
      self.waitFor(prompt, \
                   QadInputTypeEnum.POINT2D | QadInputTypeEnum.KEYWORDS, \
                   None, \
                   keyWords, QadInputModeEnum.NONE)      


   #============================================================================
   # run
   #============================================================================
   def run(self, msgMapTool = False, msg = None):
      if self.plugIn.canvas.mapRenderer().destinationCrs().geographicFlag():
         self.showMsg(QadMsg.translate("QAD", "\nThe coordinate reference system of the project must be a projected coordinate system.\n"))
         return True # fine comando

      #=========================================================================
      # RICHIESTA SELEZIONE OGGETTI LIMITI
      if self.step == 0: # inizio del comando
         CurrSettingsMsg = QadMsg.translate("QAD", "\nCurrent settings: ")
         if self.edgeMode == 0: # 0 = nessuna estensione
            CurrSettingsMsg = CurrSettingsMsg + QadMsg.translate("Command_TRIM", "Edge = No extend")
         else:
            CurrSettingsMsg = CurrSettingsMsg + QadMsg.translate("Command_TRIM", "Edge = Extend")
                  
         self.showMsg(CurrSettingsMsg)         
         self.showMsg(QadMsg.translate("Command_TRIM", "\nSelect trim limits..."))
         
         if self.SSGetClass.run(msgMapTool, msg) == True:
            # selezione terminata
            self.step = 1
            return self.run(msgMapTool, msg)        
      
      #=========================================================================
      # RISPOSTA ALLA SELEZIONE OGGETTI LIMITI
      elif self.step == 1:
         self.limitEntitySet.set(self.SSGetClass.entitySet)
         
         if self.limitEntitySet.count() == 0:
            return True # fine comando

         # si appresta ad attendere la selezione degli oggetti da estendere/tagliare
         self.waitForObjectSel()
         return False
      
      #=========================================================================
      # RISPOSTA ALLA SELEZIONE OGGETTI DA ESTENDERE
      elif self.step == 2:
         if msgMapTool == True: # il punto arriva da una selezione grafica
            # la condizione seguente si verifica se durante la selezione di un punto
            # é stato attivato un altro plugin che ha disattivato Qad
            # quindi stato riattivato il comando che torna qui senza che il maptool
            # abbia selezionato un punto            
            if self.getPointMapTool().point is None: # il maptool é stato attivato senza un punto
               if self.getPointMapTool().rightButton == True: # se usato il tasto destro del mouse
                  return True # fine comando
               else:
                  self.setMapTool(self.getPointMapTool()) # riattivo il maptool
                  return False
            else:
               value = self.getPointMapTool().point
         else: # il punto arriva come parametro della funzione
            value = msg

         if type(value) == unicode:
            if value == QadMsg.translate("Command_TRIM", "Fence") or value == "Fence":
               # Seleziona tutti gli oggetti che intersecano una polilinea
               self.PLINECommand = QadPLINECommandClass(self.plugIn)
               # se questo flag = True il comando serve all'interno di un altro comando per disegnare una linea
               # che non verrà salvata su un layer
               self.PLINECommand.virtualCmd = True   
               self.PLINECommand.run(msgMapTool, msg)
               self.step = 3
               return False               
            elif value == QadMsg.translate("Command_TRIM", "Crossing") or value == "Crossing":
               # Seleziona tutti gli oggetti che intersecano un rettangolo                                  
               self.RECTANGLECommand = QadRECTANGLECommandClass(self.plugIn)
               # se questo flag = True il comando serve all'interno di un altro comando per disegnare una linea
               # che non verrà salvata su un layer
               self.RECTANGLECommand.virtualCmd = True   
               self.RECTANGLECommand.run(msgMapTool, msg)
               self.step = 4
               return False               
            elif value == QadMsg.translate("Command_TRIM", "Edge") or value == "Edge":
               # Per estendere un oggetto usando anche le estensioni degli oggetti di riferimento
               # vedi variabile EDGEMODE
               keyWords = QadMsg.translate("Command_TRIM", "Extend") + "/" + \
                          QadMsg.translate("Command_TRIM", "No extend")
               if self.edgeMode == 0: # 0 = nessuna estensione
                  self.defaultValue = QadMsg.translate("Command_TRIM", "No")
               else: 
                  self.defaultValue = QadMsg.translate("Command_TRIM", "Extend")
               prompt = QadMsg.translate("Command_TRIM", "Specify an extension mode [{0}] <{1}>: ").format(keyWords, self.defaultValue)                        
                   
               englishKeyWords = "Extend" + "/" + "No extend"
               keyWords += "_" + englishKeyWords
               # si appresta ad attendere enter o una parola chiave         
               # msg, inputType, default, keyWords, nessun controllo
               self.waitFor(prompt, \
                            QadInputTypeEnum.KEYWORDS, \
                            self.defaultValue, \
                            keyWords, QadInputModeEnum.NONE)
               self.step = 5               
               return False               
            elif value == QadMsg.translate("Command_TRIM", "Undo") or value == "Undo":
               if self.nOperationsToUndo > 0: 
                  self.nOperationsToUndo = self.nOperationsToUndo - 1
                  self.plugIn.undoEditCommand()
               else:
                  self.showMsg(QadMsg.translate("QAD", "The command has been canceled."))
         elif type(value) == QgsPoint: # se é stato selezionato un punto
            self.entitySet.clear()
            if self.getPointMapTool().entity.isInitialized():
               self.entitySet.addEntity(self.getPointMapTool().entity)
               ToExtend = True if self.getPointMapTool().shiftKey == True else False
               self.trimFeatures(QgsGeometry.fromPoint(value), ToExtend)
            else:
               # cerco se ci sono entità nel punto indicato considerando
               # solo layer lineari editabili che non appartengano a quote
               layerList = []
               for layer in self.plugIn.canvas.layers():
                  if layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QGis.Line and layer.isEditable():
                     if len(self.plugIn.dimStyles.getDimListByLayer(layer)) == 0:
                        layerList.append(layer)
               
               result = qad_utils.getEntSel(self.getPointMapTool().toCanvasCoordinates(value),
                                            self.getPointMapTool(), \
                                            layerList)
               if result is not None:
                  feature = result[0]
                  layer = result[1]
                  point = result[2]
                  self.entitySet.addEntity(QadEntity().set(layer, feature.id()))
                  self.trimFeatures(QgsGeometry.fromPoint(point), False)
         else:
            return True # fine comando
         
         # si appresta ad attendere la selezione degli oggetti da estendere/tagliare
         self.waitForObjectSel()
                                          
         return False 

      #=========================================================================
      # RISPOSTA ALLA RICHIESTA PUNTO PER MODALITA' INTERCETTA (da step = 2)
      elif self.step == 3: # dopo aver atteso un punto si riavvia il comando
         if self.PLINECommand.run(msgMapTool, msg) == True:
            if len(self.PLINECommand.vertices) > 1:
               if msgMapTool == True: # se la polilinea arriva da una selezione grafica
                  ToExtend = True if self.getPointMapTool().shiftKey == True else False
               else:
                  ToExtend = False

               # cerco tutte le geometrie passanti per la polilinea saltando i layer punto e poligono
               # e considerando solo layer editabili       
               self.entitySet = qad_utils.getSelSet("F", self.getPointMapTool(), self.PLINECommand.vertices, \
                                                    None, False, True, False, \
                                                    True)            
               self.trimFeatures(QgsGeometry.fromPolyline(self.PLINECommand.vertices), ToExtend)
            del self.PLINECommand
            self.PLINECommand = None

            # si appresta ad attendere la selezione degli oggetti da estendere/tagliare
            self.waitForObjectSel()
            self.getPointMapTool().refreshSnapType() # aggiorno lo snapType che può essere variato dal maptool di pline                     
                                             
         return False

      #=========================================================================
      # RISPOSTA ALLA RICHIESTA PUNTO PER MODALITA' INTERSECA (da step = 2)
      elif self.step == 4: # dopo aver atteso un punto si riavvia il comando
         if self.RECTANGLECommand.run(msgMapTool, msg) == True:            
            if len(self.RECTANGLECommand.vertices) > 1:
               if msgMapTool == True: # se la polilinea arriva da una selezione grafica
                  ToExtend = True if self.getPointMapTool().shiftKey == True else False
               else:
                  ToExtend = False
               
               # cerco tutte le geometrie passanti per la polilinea saltando i layer punto e poligono
               # e considerando solo layer editabili       
               self.entitySet = qad_utils.getSelSet("F", self.getPointMapTool(), self.RECTANGLECommand.vertices, \
                                                    None, False, True, False, \
                                                    True)            
               self.trimFeatures(QgsGeometry.fromPolyline(self.RECTANGLECommand.vertices), ToExtend)
            del self.RECTANGLECommand
            self.RECTANGLECommand = None

            # si appresta ad attendere la selezione degli oggetti da estendere/tagliare
            self.waitForObjectSel()                                 
            self.getPointMapTool().refreshSnapType() # aggiorno lo snapType che può essere variato dal maptool di rectangle                     
         return False

      #=========================================================================
      # RISPOSTA ALLA RICHIESTA DI TIPO DI ESTENSIONE (da step = 2)
      elif self.step == 5: # dopo aver atteso un punto o un numero reale si riavvia il comando
         if msgMapTool == True: # il punto arriva da una selezione grafica
            # la condizione seguente si verifica se durante la selezione di un punto
            # é stato attivato un altro plugin che ha disattivato Qad
            # quindi stato riattivato il comando che torna qui senza che il maptool
            # abbia selezionato un punto            
            if self.getPointMapTool().rightButton == True: # se usato il tasto destro del mouse
               value = self.defaultValue 
            else:
               self.setMapTool(self.getPointMapTool()) # riattivo il maptool
               return False
         else: # il valore arriva come parametro della funzione
            value = msg

         if type(value) == unicode:
            if value == QadMsg.translate("Command_TRIM", "No") or value == "No":
               self.edgeMode = 0
               QadVariables.set(QadMsg.translate("Environment variables", "EDGEMODE"), self.edgeMode)
               QadVariables.save()
               # si appresta ad attendere la selezione degli oggetti da estendere/tagliare
               self.waitForObjectSel()
            elif value == QadMsg.translate("Command_TRIM", "Extend") or value == "Extend":
               self.edgeMode = 1
               QadVariables.set(QadMsg.translate("Environment variables", "EDGEMODE"), self.edgeMode)
               QadVariables.save()
               # si appresta ad attendere la selezione degli oggetti da estendere/tagliare
               self.waitForObjectSel()
         
         return False
