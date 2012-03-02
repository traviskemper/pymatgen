from __future__ import division
import warnings
import sys
sys.path.append('/home/MDEJONG1/pythonplayground/pymatgen/pymatgen_repo/pymatgen_repo') # (If one does not want to change $PYTHONPATH)
import unittest
import pymatgen
from pymatgen.io.vaspio import Poscar
from pymatgen.io.vaspio import Vasprun
from pymatgen.io.cifio import CifWriter
from pymatgen.io.cifio import CifParser
from pymatgen.core.lattice import Lattice
from pymatgen.core.structure import Structure
from pymatgen.transformations.standard_transformations import *
from pymatgen.core.structure_modifier import StructureEditor
import numpy as np
import os
import fit_elas

__author__="Maarten de Jong"
__copyright__ = "Copyright 2012, The Materials Project"
__credits__ = "Mark Asta"
__version__ = "1.0"
__maintainer__ = "Maarten de Jong"
__email__ = "maartendft@gmail.com"
__status__ = "Development"
__date__ ="Jan 24, 2012"

class DeformGeometry(object):

    def deform(self, rlxd_str, nd=0.02, ns=0.02, m=6, n=6): # this class still requires some (optional) user input
        """
        Take original geometry (as a pymatgen structure file) and apply a range of deformations. 
        Default values generally work well for metals (in my experience). However, one might need to
        make changes for material such as oxides. Also, when using e.g. DFT+U, problems with calculation
        of stress tensor may occur.

        Args: 
            rlxd_str - pymatgen structure file, containing **relaxed** geometry
            nd - maximum amount of normal strain  
            ns - maximum amount of shear strain
            m - number of normal deformations used for structural deformations, even integer required
            n - number of shear deformations used for structural deformations, even integer required
        """	
        self.msteps = np.int(m)
        self.nsteps = np.int(n)

        if m%2!=0:
            raise ValueError("m has to be even.")
         
        if n%2!=0:
            raise ValueError("n has to be even.")
        
        mystrains = np.zeros((3, 3, np.int(m*3) + np.int(n*3)))
        
        defs = np.linspace(-nd, nd, num=m+1)
        defs = np.delete(defs, np.int(m/2), 0)
        sheardef = np.linspace(-ns, ns, num=n+1)
        sheardef = np.delete(sheardef, np.int(n/2), 0)
        defstructures = dict()

        # First apply non-shear deformations
        for i1 in range(0, 3):

            for i2 in range(0, len(defs)):

                s = StructureEditor(rlxd_str)
                F = np.identity(3)
                F[i1, i1] = F[i1, i1] + defs[i2]		   # construct deformation matrix
                E = 0.5*(np.transpose(F)*F-np.eye(3))      # Green-Lagrange strain tensor
                s.apply_strain_transformation(F)           # let deformation gradient tensor act on undistorted lattice
                strain_key = '%.5f' % F[i1,i1]
                tup = (i1, i1, strain_key)				   # key to be used for defstructures dict
                defstructures[tup] = [s.modified_structure, F, E, (i1, i1)]

        # Now apply shear deformations #		
        F_index = [[0, 1], [0, 2], [1, 2]]
        for j1 in range(0, 3):
		
            for j2 in range(0, len(sheardef)):

                s = StructureEditor(rlxd_str)
                F = np.identity(3)
                F[F_index[j1][0], F_index[j1][1]] = F[F_index[j1][0], F_index[j1][1]] + sheardef[j2]
                F = np.matrix(F)						   
                E = 0.5*(np.transpose(F)*F-np.eye(3))      # Green-Lagrange strain tensor
                s.apply_strain_transformation(F)           # let deformation gradient tensor act on undistorted lattice
                strain_key = '%.5f' % F[F_index[j1][0], F_index[j1][1]]		
                tup = (F_index[j1][0], F_index[j1][1], strain_key)
                defstructures[tup] = [s.modified_structure, F, E, (F_index[j1][0], F_index[j1][1])]


        self.defstructures = defstructures
        return self.defstructures

    def append_stress_tensors(self, stress_tensor_dict):
        """
        After the ab initio engine is run, call this method to append the stress tensors to the corresponding structures,
        stored in defstructures. Residual stresses are subtracted out for increased accuracy.

        Args:
            stress_tensor_dict - a dict with  3x3 numpy matrices, containing the stresses. Key should be as defined above,
            value should be the computed stress tensor, corresponding to that specific structure.  
			
        """
        if np.int(3*(self.msteps + self.nsteps)) != len(stress_tensor_dict):
            raise ValueError("Number of stress tensors should match number of strain tensors.")

        for i in range(0, len(stress_tensor_dict)):
            self.defstructures[i].append(stress_tensor_dict[i])

        return self.defstructures

    def fit_cij(self, tol1=1.0, sym=False, origin=False):
        """
        Use the strain tensors and computed stress tensors to fit the elastic constants.
        By default, the elastic tensor is not symmetrized. For every elastic constant, we
        choose the largest set of strains for fitting the stress-strain relationship that
        obeys the "linearity criterion".

        Args:
            tol1 - tolerance used for comparing linear parts of linear and quadratic fits of elastic constants
            these may not differ by more than [tol1] GPa
            sym - specifies whether or not the elastic tensor is symmetrized
            origin - specifies whether or not the linear least squares-fit should 
            be forced to pass through the origin (zero stress-zero strain point)
        """
        self.tol1 = tol1

        Cij = np.zeros((6,6))	# elastic tensor in Voigt notation
        count = 0

        for n1 in range(0,3):	# loop over normal modes
		
            eps_tot = []
            sig_tot = []

            for n2 in range(0, np.int(self.msteps/2)):	# loop over def. magnitudes

                start_index = np.int(self.msteps/2) - n2 - 1
                end_index = np.int(self.msteps/2) + n2 + 1
                eps_array = []
                sig_array = []
                				
                for n3 in range(start_index, end_index):

                    n3 = np.int(n3 + n1*self.msteps)
                    eps_array.append(Q.defstructures[n3][2][Q.defstructures[n3][3]])                           
                    sig_array.append([Q.defstructures[n3][4][0,0],Q.defstructures[n3][4][1,1],Q.defstructures[n3][4][2,2],  
                    Q.defstructures[n3][4][0,1], Q.defstructures[n3][4][0,2], Q.defstructures[n3][4][1,2]]) 
				
                eps_tot.append(eps_array)
                sig_tot.append(sig_array)
			
            Cij_col = fit_elas.fit_elas(eps_tot, sig_tot, tol1, origin)
			
            for Cijn in range(0,6):

                Cij[Cijn, n1] = Cij_col[Cijn, 0]					# fill up elastic tensor

        for n1 in range(3,6):   # loop over shear modes

            eps_tot = []
            sig_tot = []

            for n2 in range(0, np.int(self.nsteps/2)):  # loop over def. magnitudes

                start_index = np.int(self.nsteps/2) - n2 - 1
                end_index = np.int(self.nsteps/2) + n2 + 1
                eps_array = []
                sig_array = []

                for n3 in range(start_index, end_index):

                    n3 = np.int(n3 + n1*self.nsteps)
                    eps_array.append(Q.defstructures[n3][2][Q.defstructures[n3][3]])

                    sig_array.append([Q.defstructures[n3][4][0,0],Q.defstructures[n3][4][1,1],Q.defstructures[n3][4][2,2],
                    Q.defstructures[n3][4][0,1], Q.defstructures[n3][4][0,2], Q.defstructures[n3][4][1,2]])

                eps_tot.append(eps_array)
                sig_tot.append(sig_array)

                Cij_col = fit_elas.fit_elas(eps_tot, sig_tot, tol1, origin)

                for Cijn in range(0,6):

                    Cij[Cijn, n1] = 0.5*Cij_col[Cijn, 0]			# factor 0.5 is required for shear modes only

        if sym == True:
            Cij = 0.50*(Cij + np.transpose(Cij))

        self.Cij = Cij


##### Below shows example how to use this code #####

struct = CifParser('/home/MDEJONG1/pythonplayground/pymatgen/pymatgen_repo/pymatgen_repo/pymatgen/phonons/aluminum.cif').get_structures()[0]
#Q = DeformGeometry(struct)
#Q.deform(0.015, 0.015, 6, 6)

# append stress tensor like this: #
#tens = np.eye((3))*8.0
#Q.defstructures[(0, 2, '0.00500')].append(tens)
#                                 #



#print Q.defstructures[(0, 2, '0.00500')]
#for key in Q.defstructures.keys():
#	if key[0]


#Q.get_residual_stress(np.zeros((3,3)), 1)
#stress_dict = dict()

## run VASP-calculation here ##

## continue once calculations have finished ##

#for i in range(0, 36):

#	A = Vasprun('/home/MDEJONG1/pythonplayground/pymatgen/pymatgen_repo/pymatgen_repo/pymatgen/phonons/test4/F'+str(i)+'/vasprun.xml')
#	stress_dict[i] = A.ionic_steps[-1]['stress']

#Q.append_stress_tensors(stress_dict)

#Q.fit_cij()
#print Q.Cij

#for s in Q.defstructures[3][0].sites: print s.coords, s.frac_coords

#print type(Q.defstructures[3][0])


#for c in range(0, len(Q.defstructures)):

#   w = Poscar(Q.defstructures[c][0])
#   w.write_file('POSCAR_' + str(c))

#print Q.__dict__.keys()


