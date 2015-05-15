from basic cimport *

cdef extern from "btBulletDynamicsCommon.h":
    cdef cppclass btCollisionShape:
        btCollisionShape()
        void setLocalScaling(const btVector3 &scaling)
        btVector3 &getLocalScaling()
        void calculateLocalInertia(btScalar mass, btVector3 &inertia)
        char *getName()

    cdef cppclass btConvexShape:
        btConvexShape()

    cdef cppclass btConvexInternalShape:
        btConvexInternalShape()

    cdef cppclass btPolyhedralConvexShape:
        btPolyhedralConvexShape()

    cdef cppclass btBoxShape:
        btBoxShape(btVector3)

    cdef cppclass btSphereShape:
        btSphereShape(btScalar radius)

    cdef cppclass btConcaveShape:
        btConcaveShape()

    cdef cppclass btEmptyShape:
        btEmptyShape()

    cdef cppclass btStaticPlaneShape:
        btStaticPlaneShape(btVector3 &v, btScalar plane_const)
