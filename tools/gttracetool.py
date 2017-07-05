# -*- coding: utf-8 -*-
"""
/***************************************************************************
 File Name: tools/gttacetool.py
 Last Change: 
/*************************************************************************** 
 ---------------
 GeoTools
 ---------------
 A QGIS plugin
 Collection of tools for geoscience application. Some tools can be found in 
 qCompass plugin for CloudCompare. 
 If you are publishing any work associated with this plugin please cite
 #TODO add citatioN!
                             -------------------
        begin                : 2015-01-1
        copyright          : (C) 2015 by Lachlan Grose
        email                : lachlan.grose@monash.edu
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
from PyQt4 import QtGui

from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *
from osgeo import gdal
from osgeo.gdalnumeric import *
from osgeo.gdalconst import *
import numpy as np
import time
import gttrace as trace
import uuid
import matplotlib.pyplot as plt
from skimage import filters
#import phasepack
class GtTraceTool(QgsMapToolEmitPoint):
    #deactivatedt = pyqtSignal()
    def __init__(self, canvas,iface,target,cost):
        #qgis layers/interface
        self.canvas = canvas
        self.iface = iface
        self.cost = cost
        self.target = target
        #crs reprojection stuff
        self.targetlayerCRSSrsid = self.target.crs().srsid()
        self.costlayerCRSSrsid = self.cost.crs().srsid()
        #self.renderer = self.canvas.mapRenderer()
        self.projectCRSSrsid = self.canvas.mapSettings().destinationCrs().srsid()
        if self.targetlayerCRSSrsid != self.costlayerCRSSrsid:
            print "Target and cost have different CRS"
        self.use_control_points = False
        self.use_dem_for_planes = False
        self.xmin = self.cost.extent().xMinimum()
        self.ymin = self.cost.extent().yMinimum()
        self.xmax = self.cost.extent().xMaximum()
        self.ymax = self.cost.extent().yMaximum()
        self.xsize = self.cost.rasterUnitsPerPixelX()
        self.ysize = self.cost.rasterUnitsPerPixelY()
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberBand = QgsRubberBand(self.canvas, QGis.Point)
        self.rubberBand.setColor(Qt.red)
        self.rubberBandLine = QgsRubberBand(self.canvas,QGis.Line)
        self.rubberBandLine.setColor(Qt.red)
        self.rubberBandLine.setWidth(1)
        self.trace = trace.ShortestPath()
        self.invert = False
        self.trace.set_image(self.rasterToNumpy(self.cost)) 
        self.paths = []#self.trace.shortest_path()
    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(QGis.Point)
        self.trace.remove_control_points()
        self.rubberBandLine.reset(QGis.Line)
    def clearRubberBand(self):
        if self.rubberBandLine:
            self.rubberBandLine.reset(QGis.Line)
            self.rubberBand.reset(QGis.Point)
        
    def invertCost(self,flag):
        if flag == True:
            array = self.rasterToNumpy(self.cost)
            max_v = np.max(array)
            array = max_v+1 - array
            self.trace.set_image(array)
            self.invert = True
        if flag == False:
            array = self.rasterToNumpy(self.cost)
            self.trace.set_image(array)
            self.invert = False
    def delete_control_points(self):
        if self.rubberBand:
            self.rubberBand.reset(QGis.Point)
        self.trace.remove_control_points()
    def addPoint(self,p):
        #self.rubberBand.reset(QGis.Line)
        if self.costlayerCRSSrsid != self.projectCRSSrsid:
            transform = QgsCoordinateTransform(self.costlayerCRSSrsid, 
                                            self.projectCRSSrsid)
            p = transform.transform(p)
        self.rubberBand.addPoint(p, True)
        self.rubberBand.show()     
    def removeLastPoint(self):
        if self.trace.remove_last_node() == False:
            self.rubberBandLine.reset(QGis.Line)
        self.rubberBand.removeLastPoint()
    def runTrace(self):
        self.rubberBandLine.reset(QGis.Line)
        self.paths = self.trace.shortest_path()
        s = 0
        if len(self.paths) == 0:
            return
        for c in self.paths:
            i = (c[0])
            j = (c[1])
            x_ = (float(i))*self.xsize+self.xmin+self.xsize*.5
            y_ = (float(j))*self.ysize+self.ymin+self.ysize*.5
            p = QgsPoint(x_,y_)
            if self.costlayerCRSSrsid != self.projectCRSSrsid:
                transform = QgsCoordinateTransform(self.costlayerCRSSrsid, 
                                        self.projectCRSSrsid)
                p = transform.transform(p)

            self.rubberBandLine.addPoint(p,True)
    def setControlPoints(self, vector = None):
        if vector == None:
            self.use_control_points = False
            return 
        self.use_control_points = True
        self.control_points = vector
        return
    def setDem(self,raster= None):
        if raster == None:
            print "no raster"
            self.use_dem_for_planes = False
            return
        pr = self.target.dataProvider()
        fields = pr.fields()
        strike = False
        dip = False
        e1 = False
        e2 = False
        e3 = False

        attributes = []
        for f in fields:
            if f.name() == 'DIP_DIR':
                strike = True
            if f.name() == 'E_1':
                e1 = True
            if f.name() == 'E_2':
                e2 = True
            if f.name() == 'E_3':
                e3 = True
            if f.name() == 'DIP':
                dip = True
        if not dip:
            attributes.append(QgsField("DIP",QVariant.Double))
            print "Creating DIP attribute"
        if not strike:
            attributes.append(QgsField("DIP_DIR",QVariant.Double))           
            print "Creating DIP_DIR attribute"
        if not e1:
            attributes.append(QgsField("E_1",QVariant.Double))            
            print "Creating EIGENVALUE_1 attribute"
        if not e2:
            attributes.append(QgsField("E_2",QVariant.Double))            
            print "Creating EIGENVALUE_2 attribute"
        if not e3:
            attributes.append(QgsField("E_3",QVariant.Double))            
            print "Creating EIGENVALUE_3 attribute"
            
        if len(attributes) > 0:
            pr.addAttributes(attributes)
        self.use_dem_for_planes = True
        self.dem = raster
        self.target.updateFields()
        return

    def addField(self,fieldname,fieldtype,layer):
        #slightly less optimised way to add a field but more compartmentalised
        pr = layer.dataProvider()
        fields = pr.fields()
        strike = False
        dip = False
        rms = False
        attributes = []
        for f in fields:
            if f.name() == fieldname:
                return True
        pr.addAttributes([QgsField(fieldname,fieldtype)])
        layer.updateFields()

        print "Creating and adding "+fieldname+" attribute"
        return True
    def addLine(self):
        if len(self.paths) == 0:
            return
        #if using control points add a uuid to the control point and the line
        lineuuid = uuid.uuid1()
        self.addField("COST",QVariant.String,self.target)
        if self.use_control_points:
            #add uuid to control point layer
            self.addField("UUID",QVariant.String,self.control_points)
            self.addField("UUID",QVariant.String,self.target)

            point_pr = self.control_points.dataProvider()
            point_fields = point_pr.fields()
            self.control_points.startEditing()
            pointlayerCRSSrsid = self.control_points.crs().srsid()
            
            for p in self.trace.nodes:

                fet = QgsFeature(point_fields)
                x_ = (float(p[0]))*self.xsize+self.xmin
                y_ = (float(p[1]))*self.ysize+self.ymin
                geom = QgsGeometry.fromPoint(QgsPoint(x_,y_))
                if pointlayerCRSSrsid != self.costlayerCRSSrsid:
                    geom.transform(QgsCoordinateTransform(self.costlayerCRSSrsid,
                                                      pointlayerCRSSrsid))
                fet.setGeometry(geom)
                fet['UUID'] = str(lineuuid)
                point_pr.addFeatures([fet])
            self.control_points.commitChanges()
            self.control_points.updateFields()
        vl = self.target        
        pr = vl.dataProvider()
        fields = pr.fields()
        # Enter editing mode
        vl.startEditing()
        xyz = []
        if self.use_dem_for_planes:
            if self.dem == None:
                print "No DEM selected"
                return
            filepath = self.dem.dataProvider().dataSourceUri()
            dem_src = gdal.Open(filepath)
            dem_gt = dem_src.GetGeoTransform()
            dem_rb = dem_src.GetRasterBand(1)
        
        points = []
        for c in self.paths:
            i = (c[0])
            j = (c[1])
            x_ = (float(i))*self.xsize+self.xmin + self.xsize*.5
            y_ = (float(j))*self.ysize+self.ymin + self.ysize*.5
            points.append(QgsPoint(x_, y_))
            if self.use_dem_for_planes:
                px = int((x_ - dem_gt[0]) / dem_gt[1])
                py = int((y_ - dem_gt[3]) / dem_gt[5])
                intval=dem_rb.ReadAsArray(px,py,1,1)[0][0]
                xyz.append([x_,y_,intval])
        if self.use_dem_for_planes:
            M = np.array(xyz)
            M -=  np.mean(M,axis=0)
            C = M.T.dot(M)
            eigvals, eigvec = np.linalg.eig(C)
            n = eigvec[np.argmin(eigvals)]
            if n[2] < 0:
                n[0] = -n[0]
                n[1] = -n[1]
                n[2] = -n[2] 

        fet = QgsFeature(fields)
        geom = QgsGeometry.fromPolyline(points)
        if self.targetlayerCRSSrsid != self.costlayerCRSSrsid:
            geom.transform(QgsCoordinateTransform(self.costlayerCRSSrsid,
                                              self.targetlayerCRSSrsid))


        fet.setGeometry( geom  )
        if self.invert:
            fet['COST'] = self.cost.name()+"_inverted"
        if not self.invert:
            fet['COST'] = self.cost.name()
        if self.use_dem_for_planes:
            dip_dir = 90. - np.arctan2(n[1],n[0]) * 180.0 / np.pi
            if dip_dir > 360.:
                dip_dir -= 360.
            point_type = np.sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2])
            dip = np.arccos(n[2])*180.0 / np.pi
            eigvals.sort()
            fet['DIP_DIR']= float(dip_dir)
            fet['DIP']= float(dip)
            fet['E_1'] = float(eigvals[2])
            fet['E_2'] = float(eigvals[1])
            fet['E_3'] = float(eigvals[0])
        if self.use_control_points:
            fet['UUID'] = str(lineuuid)
        vl.addFeature(fet)
        vl.commitChanges()
        vl.updateFields()
        vl.dataProvider().forceReload()
        self.rubberBandLine.reset(QGis.Line)
        self.canvas.refresh()

        self.reset()
    def keyReleaseEvent(self,e):
        if e.key() == Qt.Key_Backspace:
            self.removeLastPoint()
            self.runTrace()
            e.accept()
        if e.key() == Qt.Key_Enter:
            self.addLine()
        if e.key() == Qt.Key_Escape:
            self.reset()
    def keyPressEvent(self,e):
        if e.key() == Qt.Key_Backspace:
            e.accept()
            return
        if e.key() == Qt.Key_Enter:
            return
        if e.key() == Qt.Key_Escape:
            return
        return
    def canvasPressEvent(self, e):
        point = self.toMapCoordinates(e.pos())
        if type(self.cost) != QgsRasterLayer:
            return
        if e.button() == Qt.LeftButton:
            if self.projectCRSSrsid != self.costlayerCRSSrsid:
                transform = QgsCoordinateTransform(self.projectCRSSrsid,
                                                  self.costlayerCRSSrsid)
                point = transform.transform(point)
            i = int((point[0] - self.xmin) / self.xsize)
            j = int((point[1] - self.ymin) / self.ysize)
            self.rows = self.cost.height()
            self.columns = self.cost.width()
            j1 = j
            i1 = i
            if i < 0 or i>self.columns or j <0 or j > self.rows:
                print "out of bounds"
                return 
            self.trace.add_node([i1,j1])
            self.addPoint(point)
            self.runTrace()
        if e.button() == Qt.RightButton:
           self.addLine()
    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False
        #r = self.rectangle()
    def rasterToNumpy(self,layer):
        filepath = layer.dataProvider().dataSourceUri()
        ds = gdal.Open(filepath)
        array = np.array(ds.GetRasterBand(1).ReadAsArray()).astype('int')                     
        array = np.rot90(np.rot90(np.rot90(array)))
        return array
    def deactivate(self):
        self.delete_control_points()
        self.clearRubberBand()
        QgsMapToolEmitPoint.deactivate(self)
        #self.deactivatedt.emit()
        #slight bug when this signal is allowed to 
        #emit we get a recursive error TODO debug

    #    self.emit(SIGNAL("deactivated()"))

class CostCalculator():
    def __init__(self,layer):
        self.layer = layer
    def layer_to_numpy(self,layer):
        filepath = layer.dataProvider().dataSourceUri()
        ds = gdal.Open(filepath)
        self.transform = ds.GetGeoTransform()
        if ds == None:
            return
        self.arrays = []
        for i in range(self.layer.bandCount()):
            array = np.array(ds.GetRasterBand(i+1).ReadAsArray()).astype('int')
            self.arrays.append(np.rot90(array,3))
            print array.shape
        return self.arrays
    def numpy_to_layer(self,array,name):
        array = np.rot90(array)
        sy, sx = array.shape
        print array.shape
        pathname = name
        driver = gdal.GetDriverByName("GTiff")
        dsOut = driver.Create(pathname, sx+1,sy+1,1,gdal.GDT_Float32 ,)
        print self.transform
        dsOut.SetGeoTransform(self.transform)
        bandOut=dsOut.GetRasterBand(1)
        BandWriteArray(bandOut, array)
        bandOut = None
        dsOut = None
        layer = QgsRasterLayer(pathname,name)
        QgsMapLayerRegistry.instance().addMapLayer(layer)
    def run_calculator(self,string,name):
        if 'sobel' in string:
            array = self.calc_edges(0)
            self.numpy_to_layer(array,name) 
            return
        if 'sobh' in string:
            array = self.calc_edges(1)
            self.numpy_to_layer(array,name) 
            return
        if 'sobv' in string:
            array = self.calc_edges(2)
            self.numpy_to_layer(array,name) 
            return        
        if 'prewitt' in string:
            array = self.calc_edges(3)
            self.numpy_to_layer(array,name) 
            return 
        if 'roberts' in string:
            array = self.calc_edges(4)
            self.numpy_to_layer(array,name) 
            return 
        if 'scharr' in string:
            array = self.calc_edges(5)
            self.numpy_to_layer(array,name) 
            return             
        #if 'phase' in string:
        #    array = self.calc_edges(6)
        #    self.numpy_to_layer(array,name) 
        #    return
        if 'darkness' in string:
            array = self.calc_darkness()
            self.numpy_to_layer(array,name) 
            return            
    def calc_darkness(self):
        self.layer_to_numpy(self.layer)
        cost=np.array(self.arrays[0])
        cost.fill(0)
        for i in range(len(self.arrays)):
            cost+=self.arrays[i]
        cost /= len(self.arrays)
        return cost
        #print cost.shape
 
    def calc_edges(self,t):
        self.layer_to_numpy(self.layer)    
        if self.layer.bandCount() > 1:
            print "returning false"
            return False
        if t == 0:
            return filters.sobel(self.arrays[0].astype(float))
        if t == 1:
            return filters.sobel_h(self.arrays[0].astype(float))
        if t == 2:
            return filters.sobel_v(self.arrays[0].astype(float))    
        if t == 3:
            return filters.prewitt(self.arrays[0].astype(float))    
        if t == 4:
            return filters.roberts(self.arrays[0].astype(float))    
        if t == 5:
            return filters.scharr(self.arrays[0].astype(float))  
        #if t == 6:
        #    M, ori, ft, T = phasepack.phasecongmono(self.arrays[0].astype(float))
        #    return M
              
