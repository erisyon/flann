#Copyright 2008-2009  Marius Muja (mariusm@cs.ubc.ca). All rights reserved.
#Copyright 2008-2009  David G. Lowe (lowe@cs.ubc.ca). All rights reserved.
#
#THE BSD LICENSE
#
#Redistribution and use in source and binary forms, with or without
#modification, are permitted provided that the following conditions
#are met:
#
#1. Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
#2. Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
#THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
#IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
#OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
#IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
#INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
#NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
#THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from ctypes import *
#from ctypes.util import find_library
from numpy import float32, float64, uint8, int32, matrix, array, empty, reshape, require
from numpy.ctypeslib import load_library, ndpointer
import numpy.random as _rn
import os
from pyflann.exceptions import FLANNException
import sys

STRING = c_char_p


class CustomStructure(Structure):
    """
        This class extends the functionality of the ctype's structure
        class by adding custom default values to the fields and a way of translating
        field types.
    """
    _defaults_ = {}
    _translation_ = {}
    
    def __init__(self):
        Structure.__init__(self)
        self.__field_names = [ f for (f,t) in self._fields_]
        self.update(self._defaults_)    
    
    def update(self, dict):
        for k,v in dict.iteritems():
            if k in self.__field_names:
                setattr(self,k,self.__translate(k,v))
    
    def __getitem__(self, k):
        if k in self.__field_names:
            return self.__translate_back(k,getattr(self,k))
        
    def __setitem__(self, k, v):
        if k in self.__field_names:
            setattr(self,k,self.__translate(k,v))
        else:
            raise KeyError("No such member: "+k)
    
    def keys(self):
        return self.__field_names 

    def __translate(self,k,v):
        if k in self._translation_:
            if v in self._translation_[k]:
                return self._translation_[k][v]
        return v        

    def __translate_back(self,k,v):
        if k in self._translation_:
            for tk,tv in self._translation_[k].iteritems():
                if tv==v:
                    return tk
        return v        

class FLANNParameters(CustomStructure):
    _fields_ = [
        ('algorithm', c_int),
        ('checks', c_int),
        ('cb_index', c_float),
        ('trees', c_int),
        ('branching', c_int),
        ('iterations', c_int),
        ('centers_init', c_int),
        ('target_precision', c_float),
        ('build_weight', c_float),
        ('memory_weight', c_float),
        ('sample_fraction', c_float),
        ('log_level', c_int),
        ('random_seed', c_long),
    ]
    _defaults_ = {
        'algorithm' : 'kdtree',
        'checks' : 32,
        'cb_index' : 0.5,
        'trees' : 1,
        'branching' : 32,
        'iterations' : 5,
        'centers_init' : 'random',
        'target_precision' : -1,
        'build_weight' : 0.01,
        'memory_weight' : 0.0,
        'sample_fraction' : 0.1,
        'log_level' : "warning",
        'random_seed' : -1
  }
    _translation_ = {
            "algorithm"     : {"linear"    : 0, "kdtree"    : 1, "kmeans"    : 2, "composite" : 3, "saved": 254, "autotuned" : 255, "default"   : 1},
        "centers_init"  : {"random"    : 0, "gonzales"  : 1, "kmeanspp"  : 2, "default"   : 0},
        "log_level"     : {"none"      : 0, "fatal"     : 1, "error"     : 2, "warning"   : 3, "info"      : 4, "default"   : 2}
    }
    
    
default_flags = ['C_CONTIGUOUS', 'ALIGNED']
allowed_types = [ float32, float64, uint8, int32]   

FLANN_INDEX = c_void_p


def load_flann_library():

    root_dir = os.path.abspath(os.path.dirname(__file__))
    
    libname = 'libflann'
    if sys.platform == 'win32':
        libname = 'flann'

    flannlib = None
    loaded = False
    while (not loaded) and root_dir!="/":
        try:
           # print "Trying ",os.path.join(root_dir,'lib')
            flannlib = load_library(libname, os.path.join(root_dir,'lib'))
            loaded = True
        except Exception as e:
           # print e
            root_dir = os.path.dirname(root_dir)

    return flannlib

flannlib = load_flann_library()
if flannlib == None:
    print 'Cannot load dynamic library. Did you compile FLANN?'
    sys.exit(1)

class FlannLib: pass
flann = FlannLib()


flannlib.flann_log_verbosity.restype = None
flannlib.flann_log_verbosity.argtypes = [ 
        c_int # level
]

flannlib.flann_set_distance_type.restype = None
flannlib.flann_set_distance_type.argtypes = [ 
        c_int,
        c_int,        
]

type_mappings = ( ('float','float32'),
                  ('double','float64'),
                  ('byte','uint8'),
                  ('int','int32') )

def define_functions(str):
    for type in type_mappings:
        exec str%{'C':type[0],'numpy':type[1]}

flann.build_index = {}
define_functions(r"""
flannlib.flann_build_index_%(C)s.restype = FLANN_INDEX
flannlib.flann_build_index_%(C)s.argtypes = [ 
        ndpointer(%(numpy)s, ndim = 2, flags='aligned, c_contiguous'), # dataset
        c_int, # rows
        c_int, # cols
        POINTER(c_float), # speedup 
        POINTER(FLANNParameters)  # flann_params
]
flann.build_index[%(numpy)s] = flannlib.flann_build_index_%(C)s
""")

flann.save_index = {}
define_functions(r"""
flannlib.flann_save_index_%(C)s.restype = None
flannlib.flann_save_index_%(C)s.argtypes = [
        FLANN_INDEX, # index_id
        c_char_p #filename                                   
] 
flann.save_index[%(numpy)s] = flannlib.flann_save_index_%(C)s
""")

flann.load_index = {}
define_functions(r"""
flannlib.flann_load_index_%(C)s.restype = FLANN_INDEX
flannlib.flann_load_index_%(C)s.argtypes = [
        c_char_p, #filename                                   
        ndpointer(%(numpy)s, ndim = 2, flags='aligned, c_contiguous'), # dataset
        c_int, # rows
        c_int, # cols
]
flann.load_index[%(numpy)s] = flannlib.flann_load_index_%(C)s
""")

flann.find_nearest_neighbors = {}    
define_functions(r"""                          
flannlib.flann_find_nearest_neighbors_%(C)s.restype = c_int
flannlib.flann_find_nearest_neighbors_%(C)s.argtypes = [ 
        ndpointer(%(numpy)s, ndim = 2, flags='aligned, c_contiguous'), # dataset
        c_int, # rows
        c_int, # cols
        ndpointer(%(numpy)s, ndim = 2, flags='aligned, c_contiguous'), # testset
        c_int,  # tcount
        ndpointer(int32, ndim = 2, flags='aligned, c_contiguous, writeable'), # result
        ndpointer(float32, ndim = 2, flags='aligned, c_contiguous, writeable'), # dists
        c_int, # nn
        POINTER(FLANNParameters)  # flann_params
]
flann.find_nearest_neighbors[%(numpy)s] = flannlib.flann_find_nearest_neighbors_%(C)s
""")

flann.find_nearest_neighbors_index = {}
define_functions(r"""
flannlib.flann_find_nearest_neighbors_index_%(C)s.restype = c_int
flannlib.flann_find_nearest_neighbors_index_%(C)s.argtypes = [ 
        FLANN_INDEX, # index_id
        ndpointer(%(numpy)s, ndim = 2, flags='aligned, c_contiguous'), # testset
        c_int,  # tcount
        ndpointer(int32, ndim = 2, flags='aligned, c_contiguous, writeable'), # result
        ndpointer(float32, ndim = 2, flags='aligned, c_contiguous, writeable'), # dists
        c_int, # nn
        POINTER(FLANNParameters) # flann_params
]
flann.find_nearest_neighbors_index[%(numpy)s] = flannlib.flann_find_nearest_neighbors_index_%(C)s
""")

flann.radius_search = {}
define_functions(r"""
flannlib.flann_radius_search_%(C)s.restype = c_int
flannlib.flann_radius_search_%(C)s.argtypes = [ 
        FLANN_INDEX, # index_id
        ndpointer(%(numpy)s, ndim = 1, flags='aligned, c_contiguous'), # query
        ndpointer(int32, ndim = 1, flags='aligned, c_contiguous, writeable'), # indices
        ndpointer(float32, ndim = 1, flags='aligned, c_contiguous, writeable'), # dists
        c_int, # max_nn
        c_float, # radius
        POINTER(FLANNParameters) # flann_params
]
flann.radius_search[%(numpy)s] = flannlib.flann_radius_search_%(C)s
""")

flann.compute_cluster_centers = {}
define_functions(r"""
flannlib.flann_compute_cluster_centers_%(C)s.restype = c_int
flannlib.flann_compute_cluster_centers_%(C)s.argtypes = [ 
        ndpointer(%(numpy)s, ndim = 2, flags='aligned, c_contiguous'), # dataset
        c_int,  # rows
        c_int,  # cols
        c_int,  # clusters 
        ndpointer(float32, flags='aligned, c_contiguous, writeable'), # result
        POINTER(FLANNParameters)  # flann_params
]
flann.compute_cluster_centers[%(numpy)s] = flannlib.flann_compute_cluster_centers_%(C)s
""")
# double is an exception
flannlib.flann_compute_cluster_centers_double.restype = c_int
flannlib.flann_compute_cluster_centers_double.argtypes = [ 
        ndpointer(float64, ndim = 2, flags='aligned, c_contiguous'), # dataset
        c_int,  # rows
        c_int,  # cols
        c_int,  # clusters 
        ndpointer(float64, flags='aligned, c_contiguous, writeable'), # result
        POINTER(FLANNParameters)  # flann_params
]


flann.free_index = {}
define_functions(r"""
flannlib.flann_free_index_%(C)s.restype = None
flannlib.flann_free_index_%(C)s.argtypes = [ 
        FLANN_INDEX,  # index_id
        POINTER(FLANNParameters) # flann_params
]
flann.free_index[%(numpy)s] = flannlib.flann_free_index_%(C)s
""")

flannlib.compute_ground_truth_float.restype = None
flannlib.compute_ground_truth_float.argtypes = [ 
        ndpointer(float32, ndim = 2, flags='aligned, c_contiguous'), # dataset
        c_int*2, # dshape
        ndpointer(float32, ndim = 2, flags='aligned, c_contiguous'), # testset
        c_int*2, # tshape
        ndpointer(int32, ndim = 2, flags='aligned, c_contiguous, writeable'), # matches
        c_int * 2, # mshape
        c_int # skip
]

flannlib.test_with_precision.restype = c_float
flannlib.test_with_precision.argtypes = [
        FLANN_INDEX, 
        ndpointer(float32, ndim = 2, flags='aligned, c_contiguous'), # dataset
        c_int*2, # dshape
        ndpointer(float32, ndim = 2, flags='aligned, c_contiguous'), # testset
        c_int*2, # tshape
        ndpointer(int32, ndim = 2, flags='aligned, c_contiguous'), # matches
        c_int*2, # mshape
        c_int, # nn
        c_float, #precision
        POINTER(c_int), # checks
        c_int # skip
]


flannlib.test_with_checks.restype = c_float
flannlib.test_with_checks.argtypes = [
        FLANN_INDEX, 
        ndpointer(float32, ndim = 2, flags='aligned, c_contiguous'), # dataset
        c_int*2, # dshape
        ndpointer(float32, ndim = 2, flags='aligned, c_contiguous'), # testset
        c_int*2, # tshape
        ndpointer(int32, ndim = 2, flags='aligned, c_contiguous'), # matches
        c_int*2, # mshape
        c_int, # nn
        c_int, # checks
        POINTER(c_float), #precision
        c_int # skip
]



def ensure_2d_array(array, flags, **kwargs):
    array = require(array, requirements = flags, **kwargs) 
    if len(array.shape) == 1:
        array.shape = (-1,array.size)
    return array


def compute_ground_truth(dataset, testset, nn, skip = 0):
    
    dataset = ensure_2d_array(dataset,default_flags, dtype=float32) 
    testset = ensure_2d_array(testset,default_flags, dtype=float32) 
    
    assert(dataset.shape[1] == testset.shape[1] )
    match = empty((testset.shape[0],nn), dtype=int32)
    
    flannlib.compute_ground_truth_float(dataset, dataset.ctypes.shape, testset, testset.ctypes.shape, match, match.ctypes.shape, skip)
    return match


def test_with_precision(index, dataset, testset, matches, precision, nn, skip = 0):
    dataset = ensure_2d_array(dataset,default_flags, dtype=float32) 
    testset = ensure_2d_array(testset,default_flags, dtype=float32) 
    matches = ensure_2d_array(matches,default_flags, dtype=int32)
    
    assert(dataset.shape[1] == testset.shape[1] )
    assert(testset.shape[0] == matches.shape[0] )
    assert( nn <= matches.shape[1] )
    
    checks = c_int(0)
    time = flannlib.test_with_precision(index, dataset, dataset.ctypes.shape, testset, testset.ctypes.shape, matches, matches.ctypes.shape, 
                        nn, precision, byref(checks), skip)
    
    return checks.value, time
    
def test_with_checks(index, dataset, testset, matches, checks, nn, skip = 0):
    dataset = ensure_2d_array(dataset,default_flags, dtype=float32) 
    testset = ensure_2d_array(testset,default_flags, dtype=float32) 
    matches = ensure_2d_array(matches,default_flags, dtype=int32)
    
    assert(dataset.shape[1] == testset.shape[1] )
    assert(testset.shape[0] == matches.shape[0] )
    assert( nn <= matches.shape[1] )
    
    precision = c_float(0)
    time = flannlib.test_with_checks(index, dataset, dataset.ctypes.shape, testset, testset.ctypes.shape, matches, matches.ctypes.shape, 
                            nn, checks, byref(precision), skip)
    
    return precision.value, time



index_type = int32


# This class is derived from an initial implementation by Hoyt Koepke (hoytak@cs.ubc.ca)
class FLANN:
    """
    This class defines a python interface to the FLANN lirary.
    """
    __rn_gen = _rn.RandomState()
    
    _as_parameter_ = property( lambda self: self.__curindex )

    def __init__(self, **kwargs):
        """
        Constructor for the class and returns a class that can bind to
        the flann libraries.  Any keyword arguments passed to __init__
        override the global defaults given.
        """
        
        self.__rn_gen.seed()

        self.__curindex = None
        self.__curindex_data = None
        self.__curindex_type = None
        
        self.__flann_parameters = FLANNParameters()        
        self.__flann_parameters.update(kwargs)

    def __del__(self):
        self.delete_index()

        
    ################################################################################
    # actual workhorse functions


    def set_distance_type(self, distance_type, order = 0):
        """
        Sets the distance type used. Possible values: euclidean, manhattan, minkowski.
        """
        
        distance_translation = { "euclidean" : 1, "manhattan" : 2, "minkowski" : 3}
        flannlib.flann_set_distance_type(distance_translation[distance_type],order)


    def nn(self, pts, qpts, num_neighbors = 1, **kwargs):
        """
        Returns the num_neighbors nearest points in dataset for each point
        in testset.
        """
        
        if not pts.dtype.type in allowed_types:
            raise FLANNException("Cannot handle type: %s"%pts.dtype)

        if not qpts.dtype.type in allowed_types:
            raise FLANNException("Cannot handle type: %s"%pts.dtype)

        if pts.dtype != qpts.dtype:
            raise FLANNException("Data and query must have the same type")
        
        pts = ensure_2d_array(pts,default_flags) 
        qpts = ensure_2d_array(qpts,default_flags) 

        npts, dim = pts.shape
        nqpts = qpts.shape[0]

        assert(qpts.shape[1] == dim)
        assert(npts >= num_neighbors)

        result = empty( (nqpts, num_neighbors), dtype=index_type)
        dists = empty( (nqpts, num_neighbors), dtype=float32)
                
        self.__flann_parameters.update(kwargs)

        flann.find_nearest_neighbors[pts.dtype.type](pts, npts, dim, 
                                                     qpts, nqpts, result, dists, num_neighbors, 
                                                     pointer(self.__flann_parameters))

        if num_neighbors == 1:
            return (result.reshape( nqpts ), dists.reshape(nqpts))
        else:
            return (result,dists)


    def build_index(self, pts, **kwargs):
        """
        This builds and internally stores an index to be used for
        future nearest neighbor matchings.  It erases any previously
        stored indexes, so use multiple instances of this class to
        work with multiple stored indices.  Use nn_index(...) to find
        the nearest neighbors in this index.

        pts is a 2d numpy array or matrix. All the computation is done
        in float32 type, but pts may be any type that is convertable
        to float32. 
        """
        
        if not pts.dtype.type in allowed_types:
            raise FLANNException("Cannot handle type: %s"%pts.dtype)

        pts = ensure_2d_array(pts,default_flags) 
        npts, dim = pts.shape
        
        self.__ensureRandomSeed(kwargs)
        
        self.__flann_parameters.update(kwargs)

        if self.__curindex != None:
            flann.free_index[self.__curindex_type](self.__curindex, pointer(self.__flann_parameters))
            self.__curindex = None
                
        speedup = c_float(0)
        self.__curindex = flann.build_index[pts.dtype.type](pts, npts, dim, byref(speedup), pointer(self.__flann_parameters))
        self.__curindex_data = pts
        self.__curindex_type = pts.dtype.type
        
        params = dict(self.__flann_parameters)
        params["speedup"] = speedup.value
        
        return params


    def save_index(self, filename):
        """
        This saves the index to a disk file.
        """
        
        if self.__curindex != None:
            flann.save_index[self.__curindex_type](self.__curindex, c_char_p(filename))

    def load_index(self, filename, pts):
        """
        Loads an index previously saved to disk.
        """
                
        if not pts.dtype.type in allowed_types:
            raise FLANNException("Cannot handle type: %s"%pts.dtype)

        pts = ensure_2d_array(pts,default_flags) 
        npts, dim = pts.shape

        if self.__curindex != None:
            flann.free_index[self.__curindex_type](self.__curindex, pointer(self.__flann_parameters))
            self.__curindex = None
            self.__curindex_data = None
            self.__curindex_type = None
        
        self.__curindex = flann.load_index[pts.dtype](c_char_p(filename), pts, npts, dim)
        self.__curindex_data = pts
        self.__curindex_type = pts.dtype.type

    def nn_index(self, qpts, num_neighbors = 1, **kwargs):
        """
        For each point in querypts, (which may be a single point), it
        returns the num_neighbors nearest points in the index built by
        calling build_index.
        """

        if self.__curindex == None:
            raise FLANNException("build_index(...) method not called first or current index deleted.")

        if not qpts.dtype.type in allowed_types:
            raise FLANNException("Cannot handle type: %s"%pts.dtype)

        if self.__curindex_type != qpts.dtype.type:
            raise FLANNException("Index and query must have the same type")

        qpts = ensure_2d_array(qpts,default_flags) 

        npts, dim = self.__curindex_data.shape

        if qpts.size == dim:
            qpts.reshape(1, dim)

        nqpts = qpts.shape[0]

        assert(qpts.shape[1] == dim)
        assert(npts >= num_neighbors)
        
        result = empty( (nqpts, num_neighbors), dtype=index_type)
        dists = empty( (nqpts, num_neighbors), dtype=float32)

        self.__flann_parameters.update(kwargs)

        flann.find_nearest_neighbors_index[self.__curindex_type](self.__curindex, 
                    qpts, nqpts,
                    result, dists, num_neighbors,
                    pointer(self.__flann_parameters))

        if num_neighbors == 1:
            return (result.reshape( nqpts ), dists.reshape( nqpts ))
        else:
            return (result,dists)
        
        
    def nn_radius(self, query, radius, **kwargs):
        
        if self.__curindex == None:
            raise FLANNException("build_index(...) method not called first or current index deleted.")

        if not query.dtype.type in allowed_types:
            raise FLANNException("Cannot handle type: %s"%pts.dtype)

        if self.__curindex_type != qpts.dtype.type:
            raise FLANNException("Index and query must have the same type")

        npts, dim = self.__curindex_data.shape        
        assert(query.shape[0]==dim)
        
        result = empty( npts, dtype=index_type)
        dists = empty( npts, dtype=float32)
        
        self.__flann_parameters.update(kwargs)

        nn = flann.radius_search[self.__curindex_type](self.__curindex, query, 
                                         result, dists, npts,
                                         radius, pointer(self.__flann_parameters))
        
        
        return (result[0:nn],dists[0:nn])

    def delete_index(self, **kwargs):
        """
        Deletes the current index freeing all the momory it uses. 
        The memory used by the dataset that was indexed is not freed.
        """

        self.__flann_parameters.update(kwargs)
        
        if self.__curindex != None:
            flann.free_index[self.__curindex_type](self.__curindex, pointer(self.__flann_parameters))
            self.__curindex = None
            self.__curindex_data = None

    ##########################################################################################
    # Clustering functions

    def kmeans(self, pts, num_clusters, centers_init = "random", 
               max_iterations = None,
               dtype = None, **kwargs):
        """
        Runs kmeans on pts with num_clusters centroids.  Returns a
        numpy array of size num_clusters x dim.  

        If max_iterations is not None, the algorithm terminates after
        the given number of iterations regardless of convergence.  The
        default is to run until convergence.

        If dtype is None (the default), the array returned is the same
        type as pts.  Otherwise, the returned array is of type dtype.  

        """
        
        if int(num_clusters) != num_clusters or num_clusters < 1:
            raise FLANNException('num_clusters must be an integer >= 1')
        
        if num_clusters == 1:
            if dtype == None or dtype == pts.dtype:
                return mean(pts, 0).reshape(1, pts.shape[1])
            else:
                return dtype.type(mean(pts, 0).reshape(1, pts.shape[1]))

        return self.hierarchical_kmeans(pts, int(num_clusters), 1, 
                                        max_iterations, 
                                        dtype, **kwargs)
        
    def hierarchical_kmeans(self, pts, branch_size, num_branches,
                            max_iterations = None, 
                            dtype = None, **kwargs):
        """
        Clusters the data by using multiple runs of kmeans to
        recursively partition the dataset.  The number of resulting
        clusters is given by (branch_size-1)*num_branches+1.
        
        This method can be significantly faster when the number of
        desired clusters is quite large (e.g. a hundred or more).
        Higher branch sizes are slower but may give better results.

        If dtype is None (the default), the array returned is the same
        type as pts.  Otherwise, the returned array is of type dtype.  
        
        """
        
        # First verify the paremeters are sensible.

        if not pts.dtype.type in allowed_types:
            raise FLANNException("Cannot handle type: %s"%pts.dtype)

        if int(branch_size) != branch_size or branch_size < 2:
            raise FLANNException('branch_size must be an integer >= 2.')

        branch_size = int(branch_size)

        if int(num_branches) != num_branches or num_branches < 1:
            raise FLANNException('num_branches must be an integer >= 1.')

        num_branches = int(num_branches)

        if max_iterations == None: 
            max_iterations = -1
        else:
            max_iterations = int(max_iterations)


        # init the arrays and starting values
        pts = ensure_2d_array(pts,default_flags) 
        npts, dim = pts.shape
        num_clusters = (branch_size-1)*num_branches+1;
        
        if pts.dtype.type == float64:
            result = empty( (num_clusters, dim), dtype=float64)
        else:
            result = empty( (num_clusters, dim), dtype=float32)

        # set all the parameters appropriately
        
        self.__ensureRandomSeed(kwargs)
        
        params = {"iterations"       : max_iterations,
                    "algorithm"        : 'kmeans',
                    "branching"        : branch_size,
                    "random_seed"      : kwargs['random_seed']}
        
        self.__flann_parameters.update(params)
        
        numclusters = flann.compute_cluster_centers[pts.dtype.type](pts, npts, dim,
                                        num_clusters, result, 
                                        pointer(self.__flann_parameters))
        if numclusters <= 0:
            raise FLANNException('Error occured during clustering procedure.')

        if dtype == None:
            return result
        else:
            return dtype.type(result)
        
    ##########################################################################################
    # internal bookkeeping functions

        
    def __ensureRandomSeed(self, kwargs):
        if not 'random_seed' in kwargs:
            kwargs['random_seed'] = self.__rn_gen.randint(2**30)
        
