#  bpyFoil.py
#  
#  Copyright 2013 Louay Cheikh <brotherlu@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  

"""
bpyFoil is intended to import airfoil DAT files into blender and create
a surface with the points
"""

import bpy
import re, random
from bpy.types import Operator, Panel, PropertyGroup, UIList
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, FloatProperty

bl_info =   {   
            'name':'Blender Airfoil Importer',
            'category':'Object',
            'author':'Louay Cheikh',
            'version':(0,6),
            'blender':(2,67,0),
            'location':'Search Menu'
            }

def createMesh(objname,Vert,Edges=[],Faces=[]):
    """Helper Function to Create Meshes"""
    me = bpy.data.meshes.new(objname)
    ob = bpy.data.objects.new(objname,me)
    bpy.context.scene.objects.link(ob)
    
    me.from_pydata(Vert,Edges,Faces)
    me.update(calc_edges=True)

def getAirfoilName(filename):
    try:
        f = open(filename,'r')
        filename = f.readline()
        return filename.strip()
    except:
        return "NOT FOUND"

# Airfoil Class

class AirFoil:
    def __init__(self,FoilName,Resolution=250):
        
        FF = open(FoilName,'r')
        data = FF.readlines()
        
        # Create the regexp for finding the data
        r = re.compile('[.\S]*\.[0-9]*')
        # Get FoilName from the file
        self.FoilName = data[0].strip()
        # Create the coordintes from the regler exp
        FoilCoords = [r.findall(x) for x in data[1:]]
        # Convert the strings to Floats
        self.__RawPoints = [(float(x[0]),float(x[1])) for x in FoilCoords if len(x)==2 ]
        # Ensure the First point is not the Point Count that some DAT files include
        if self.__RawPoints[0][0]>1: self.__RawPoints.remove(self.__RawPoints[0])
        
        self.__ProcPoints = []
        self.__upper = []
        self.__lower = []
        self.__procPointsCount = Resolution
    
    def __str__(self):
        return "Airfoil Process Object, Last Processed: %s" % (self.FoilName)

    def processFoil(self):
        """Process Airfoils to Generate Points for Multisection solids"""
        
        # Split airfoil in upper and lower portions
        self.__airfoilSplit()
        
        # Interpolate
        self.__hinterpolate()
        
    def __airfoilSplit(self):
        """Process to divide the foildata to upper and lower sections"""
        # Find the chord coordiantes
        trailing = min(self.__RawPoints,key=lambda x:x[0])
        leading = max(self.__RawPoints,key=lambda x:x[0])
        
        # Find chord coordinates index
        trailingloc = self.__RawPoints.index(trailing)
        leadingloc = self.__RawPoints.index(leading)
        splitloc = leadingloc if 0 < leadingloc < len(self.__RawPoints)-3 else trailingloc
        
        # Split the airfoil along chord
        self.__upper = self.__RawPoints[:splitloc+1]
        self.__lower = self.__RawPoints[splitloc+1:]
        
        # Ensure each section starts at (0,0)->(1,0)
        if self.__upper[0][0] > self.__upper[-1][0]:
            self.__upper.reverse()
        if self.__lower[0][0] > self.__lower[-1][0]:
            self.__lower.reverse()
        
        # Ensure that the foils are not reversed
        testpoint = random.randint(0,min([len(self.__upper),len(self.__lower)])-1)
        if self.__upper[testpoint][1] < self.__lower[testpoint][1]:
            self.__upper , self.__lower = self.__lower , self.__upper
        
    def __hinterpolate(self):
        """Process of interpolation using piecewise hermite curve interpolation"""
        
        # Temp. Data holders
        upperint = []
        lowerint = []
        
        # Create points
        xpointsU = list(map(lambda x:x/float(self.__procPointsCount),range(0,self.__procPointsCount+1)))
        xpointsL = list(map(lambda x:x/float(self.__procPointsCount),range(0,self.__procPointsCount+1)))
                
        # Calculate secants
        uppersec = [(self.__upper[i+1][1]-self.__upper[i][1])/(self.__upper[i+1][0]-self.__upper[i][0]) for i in range(len(self.__upper)-1)]
        lowersec = [(self.__lower[i+1][1]-self.__lower[i][1])/(self.__lower[i+1][0]-self.__lower[i][0]) for i in range(len(self.__lower)-1)]
        
        # Calculate tangents
        uppertan = [(uppersec[k-1]+uppersec[k])/2 for k in range(1,len(uppersec))]
        uppertan.insert(0,uppersec[0])
        uppertan.append(uppersec[-1])

        lowertan = [(lowersec[k-1]+lowersec[k])/2 for k in range(1,len(lowersec))]
        lowertan.insert(0,lowersec[0])
        lowertan.append(lowersec[-1])
        
        # Hermite blending functions
        p0 = lambda t: 2*t**3 - 3*t**2 + 1
        m0 = lambda t: t**3 - 2*t**2 + t
        p1 = lambda t: -2*t**3 + 3*t**2
        m1 = lambda t: t**3 - t**2
        
        # Find matching points to improve accuarcy
        matchU = [(i,j) for i in range(len(xpointsU)) for j in range(len(self.__upper)) if xpointsU[i] == self.__upper[j][0]]
        matchL = [(i,j) for i in range(len(xpointsL)) for j in range(len(self.__lower)) if xpointsL[i] == self.__lower[j][0]]
        
        # Reverse match pairs to insure no index errors
        matchU.reverse()
        matchL.reverse()
        
        # Pop xpoints that dont require interpolation and append the point into the upperint list
        for i in matchU:
            xpointsU.pop(i[0])
            upperint.append(self.__upper[i[1]])
        
        # Same process as above but for lower airfoil
        for i in matchL:
            xpointsL.pop(i[0])
            lowerint.append(self.__lower[i[1]])
        
        # Interpolate upper points
        for xp in xpointsU:
            for i in range(len(self.__upper)-1):
                if self.__upper[i][0] < xp < self.__upper[i+1][0]:
                    h = self.__upper[i+1][0]-self.__upper[i][0]
                    t = (xp - self.__upper[i][0]) / h
                    solution = ( p0(t)*self.__upper[i][1] + h*m0(t)*uppertan[i] + p1(t)*self.__upper[i+1][1] + h*m1(t)*uppertan[i+1] )
                    upperint.append((xp,solution))
        
        # Interpolate lower points
        for xp in xpointsL:
            for i in range(len(self.__lower)-1):
                if self.__lower[i][0] < xp < self.__lower[i+1][0]:
                    h = self.__lower[i+1][0]-self.__lower[i][0]
                    t = (xp - self.__lower[i][0]) / h
                    solution = ( p0(t)*self.__lower[i][1] + h*m0(t)*lowertan[i] + p1(t)*self.__lower[i+1][1] + h*m1(t)*lowertan[i+1] )
                    lowerint.append((xp,solution))
        
        # Sort the points to keep the correct sequence
        upperint.sort(key=lambda x:x[0], reverse=True)
        lowerint.sort(key=lambda x:x[0])
        
        # Do checks to insure no duplicates
        if upperint[0][0] != 1.0: upperint.insert(0,(1.0,0.0))
        if upperint[-1][0] != 0.0: upperint.append((0.0,0.0))
        if lowerint[0][0] == 0.0: lowerint.pop(0)
        if lowerint[-1][0] != 1.0: lowerint.append((1.0,0.0))

        self.__ProcPoints = upperint + lowerint
        
                    
    def getRawPoints(self):
        """Return Raw Points"""
        return self.__RawPoints
    
    def getProcPoints(self):
        """Return Generated Points"""
        if self.__ProcPoints == []:
            print("Points were not Generated. Call method 'processFoil'.")
            return
        return self.__ProcPoints

# Operator Class

class bpyAirfoil(Operator):
    """ Addon to import airfoil Dat files """
    bl_idname = "object.bpyairfoil"
    bl_label = "Airfoil DAT File Importer"
    bl_options = {'REGISTER','UNDO'}

    def execute(self, context):
        """ Import """
        
        sce = context.scene
        afl = sce.airfoil_collection
        
        afl_sorted = sorted(afl,key=lambda x:x.loc_y)
        
        for F in afl_sorted:
            if F.use:
                FF = AirFoil(F.file_name,Resolution=sce.airfoil_resolution)
                FF.processFoil()
                F.verts = [(x,F.loc_y,z) for x,z in FF.getProcPoints()]
                F.verts.pop()
                F.faces = [(i,i+1,len(F.verts)-1*(i+1),len(F.verts)-1*i) for i in range(1,int(len(F.verts)/2))]
                F.faces.append((0,1,len(F.verts)-1,0)) # Add Tip Triangle
                createMesh(FF.FoilName,F.verts,Faces=F.faces)

        return {'FINISHED'}

# Panel Class Definition

class Airfoil_Collection_add(Operator):
    bl_idname = "airfoil_collection.add"
    bl_label = "Add Airfoil"
    bl_description = "Add Airfoil"
    
    def invoke(self,context,event):
        sce = context.scene
        afl = sce.airfoil_collection
        
        new_airfoil = afl.add()
        
        return {'FINISHED'}

class Airfoil_Collection_del(Operator):
    bl_idname = "airfoil_collection.remove"
    bl_label = "Remove Airfoil"
    bl_description = "Remove Airfoil"
    
    def invoke(self,context,event):
        sce = context.scene
        afl = sce.airfoil_collection
        
        if sce.airfoil_collection_idx >= 0:
            afl.remove(sce.airfoil_collection_idx)
            sce.airfoil_collection_idx-=1
        
        return {'FINISHED'}

# Airfoil Tool Panel 
class Airfoil_Panel(Panel):
    bl_label = "Airfoil Tools Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOL_PROPS"
    
    def draw(self,context):
        layout = self.layout
        scn = context.scene
        
        layout.label("Interpolation Resolution")
        row = layout.row(align=True)
        row.prop(scn,'airfoil_resolution')
        
        layout.label("Airfoil List")
        row = layout.row()
        row.template_list('Airfoil_UL_List','airfoil_collection_id',scn,"airfoil_collection",scn,"airfoil_collection_idx",rows=5)
        
        col = row.column(align=True)
        col.operator('airfoil_collection.add',text="",icon="ZOOMIN")
        col.operator('airfoil_collection.remove',text="",icon="ZOOMOUT")
        
        if len(scn.airfoil_collection) > 0:
            airfoil_item = scn.airfoil_collection[scn.airfoil_collection_idx]
            layout.prop(airfoil_item,'file_name')
            layout.prop(airfoil_item,'loc_y')
            
            layout.operator("object.bpyairfoil",text="Import Airfoils",icon="MESH_DATA")

# Create Airfoil List Classes    
class AirfoilListItem(PropertyGroup):
    file_name = StringProperty(name="Filename", subtype="FILE_PATH", description="DAT file location")
    use = BoolProperty(name="Enable",default=True,description="Enable Foil")
    loc_y = FloatProperty(name="Distance from root",min=0.0,default=0.0)

# Template list draw_item Class
class Airfoil_UL_List(UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        if self.layout_type in {'DEFAULT','COMPACT'}:
            layout.label(text=getAirfoilName(item.file_name) if item else "", translate=False)
            layout.label(text=str(item.loc_y))
            layout.prop(item,"use",text="")

def register():
    """ Register all Classes """

    # Register types for data storage
    bpy.utils.register_class(AirfoilListItem) # Register the Class List Items
    bpy.types.Scene.airfoil_collection_id = IntProperty()
    bpy.types.Scene.airfoil_collection = CollectionProperty(type=AirfoilListItem)
    bpy.types.Scene.airfoil_collection_idx = IntProperty(min=-1, max=100, default=-1)
    bpy.types.Scene.airfoil_resolution = IntProperty(name="",default=250, min=10, max=1000)
    
    # Add Template_list methods
    bpy.utils.register_class(Airfoil_Collection_add)
    bpy.utils.register_class(Airfoil_Collection_del)
    bpy.utils.register_class(Airfoil_UL_List)
    
    # Register Operator
    bpy.utils.register_class(bpyAirfoil)
    bpy.utils.register_class(Airfoil_Panel)

def unregister():
    """ Unregister all Classes """
    bpy.utils.unregister_class(AirfoilListItem)
    bpy.utils.unregister_class(Airfoil_Collection_add)
    bpy.utils.unregister_class(Airfoil_Collection_del)
    
    bpy.utils.unregister_class(bpyAirfoil)
    bpy.utils.unregister_class(Airfoil_Panel)

if __name__ == "__main__":
    register()
