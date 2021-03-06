import numpy as np

from ..util import three_dimensionalize, euclidean, unitize
from ..constants import log
from ..constants import tol_path as tol
from ..constants import res_path as res
from .intersections import line_line


def arc_center(points):
    '''
    Given three points of an arc, find the center, radius, normal, and angle.

    This uses the fact that the intersection of the perpendicular
    bisectors of the segments between the control points is the center of the arc.

    Arguments
    ---------
    points: (3,d) list of points where (d in [2,3])

    Returns
    ---------
    result: dict, with keys:
        'center':   (d,) float, cartesian center of the arc
        'radius':   float, radius of the arc
        'normal':   (3,) float, the plane normal.
        'angle':    (2,) float, angle of start and end, in radians
        'span' :    float, angle swept by the arc, in radians
    '''
    # it's a lot easier to treat 2D as 3D with a zero Z value
    is_2D, points = three_dimensionalize(points, return_2D=True)

    # find the two edge vectors of the triangle
    edge_direction = np.diff(points, axis=0)
    edge_midpoints = (edge_direction * .5) + points[0:2]

    # three points define a plane, so we find its normal vector
    plane_normal = unitize(np.cross(*edge_direction[::-1]))
    vector_edge = unitize(edge_direction)
    vector_perpendicular = unitize(np.cross(vector_edge, plane_normal))

    intersects, center = line_line(edge_midpoints, vector_perpendicular)

    if not intersects:
        raise ValueError('Segments do not intersect!')

    radius = euclidean(points[0], center)
    vector = unitize(points - center)
    angle = np.arccos(np.clip(np.dot(*vector[[0, 2]]), -1.0, 1.0))
    large_arc = (abs(angle) > tol.zero and
                 np.dot(*edge_direction) < 0.0)
    if large_arc:
        angle = (np.pi * 2) - angle

    angles = np.arctan2(*vector[:, 0:2].T[::-1]) + np.pi * 2
    angles_sorted = np.sort(angles[[0, 2]])
    reverse = angles_sorted[0] < angles[1] < angles_sorted[1]
    angles_sorted = angles_sorted[::(1 - int(not reverse) * 2)]

    result = {'center': center[:(3 - is_2D)],
              'radius': radius,
              'normal': plane_normal,
              'span': angle,
              'angles': angles_sorted}
    return result


def discretize_arc(points, close=False, scale=1.0):
    '''
    Returns a version of a three point arc consisting of line segments

    Arguments
    ---------
    points: (n, d) points on the arc where d in [2,3]
    close:  boolean, if True close the arc (circle)

    Returns
    ---------
    discrete: (m, d)
    points: either (3,3) or (3,2) of points for arc going from
            points[0] to points[2], going through control point points[1]
    '''
    two_dimensional, points = three_dimensionalize(points, return_2D=True)
    center_info = arc_center(points)
    center, R, N, angle = (center_info['center'],
                           center_info['radius'],
                           center_info['normal'],
                           center_info['span'])
    if close:
        angle = np.pi * 2

    # the number of facets, based on the angle critera
    count_a = angle / res.seg_angle
    count_l = ((R * angle)) / (res.seg_frac * scale)

    count = np.max([count_a, count_l])
    # force at LEAST 4 points for the arc, otherwise the endpoints will diverge
    count = np.clip(count, 4, np.inf)
    count = int(np.ceil(count))

    V1 = unitize(points[0] - center)
    V2 = unitize(np.cross(-N, V1))
    t = np.linspace(0, angle, count)

    discrete = np.tile(center, (count, 1))
    discrete += R * np.cos(t).reshape((-1, 1)) * np.tile(V1, (count, 1))
    discrete += R * np.sin(t).reshape((-1, 1)) * np.tile(V2, (count, 1))

    if not close:
        arc_dist = np.linalg.norm(points[[0, -1]] - discrete[[0, -1]], axis=1)
        arc_ok = (arc_dist < tol.merge).all()
        if not arc_ok:
            log.warn(
                'Failed to discretize arc (endpoint distance %s)', str(arc_dist))
            log.warn('Failed arc points: %s', str(points))
            raise ValueError('Arc endpoints diverging!')
    discrete = discrete[:, 0:(3 - two_dimensional)]

    return discrete


def arc_tangents(points):
    '''
    returns tangent vectors for points
    '''
    two_dimensional, points = three_dimensionalize(points, return_2D=True)
    center, R, N, angle = arc_center(points)
    vectors = points - center
    tangents = unitize(np.cross(vectors, N))
    return tangents[:, 0:(3 - two_dimensional)]


def arc_offset(points, distance):
    two_dimensional, points = three_dimensionalize(points)
    center, R, N, angle = arc_center(points)
    vectors = unitize(points - center)
    new_points = center + vectors * distance
    return new_points[:, 0:(3 - two_dimensional)]


def angles_to_threepoint(angles, center, radius):
    if angles[1] < angles[0]:
        angles[1] += np.pi * 2
    angles = np.array([angles[0], np.mean(angles),
                       angles[1]], dtype=np.float64)
    planar = np.column_stack((np.cos(angles), np.sin(angles))) * radius
    return planar + center
