from scipy.spatial import KDTree
from tqdm import tqdm

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from .observer import transformToChromaticity, getHeringMatrix
from .spectra import Spectra
from .maxbasis import MaxBasis
import numpy as np

def sampleCubeMapFaces(list_of_faces, samples_per_line=5):
    step = 1/samples_per_line
    xi = np.arange(0, 1, step) + (1/2*step)
    output = []
    for face in list_of_faces: # bilinear interpolation of a square face
        one_face = []
        for i in xi:
            for j in xi:
                e =  face[0] + i * (face[1] - face[0]);
                f = face[2] + i * (face[3] - face[2]);
                p = e + j*(f - e);
                one_face +=[p]
        output += [one_face]
    return np.array(output)


def plotTogether(ax, chrom_pts, sphere_pts):

    ax.scatter(chrom_pts[:, 0], chrom_pts[:, 1], chrom_pts[:, 2], c='b', alpha=0.1, label="printer")
    ax.scatter(sphere_pts[:, 0], sphere_pts[:, 1], sphere_pts[:, 2], c='r', label="sphere")

    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('z')

class CubeMap:
    """
    CubeMap class to generate a cube map from a cone basis point cloud and a set of associated rgbs or refs/wavelengths
    """
    def __init__(self, point_cloud, maxBasis: MaxBasis, rgbs=None, refs=None, ref_wavelengths=None, verbose: bool=False) -> None:
        if maxBasis.dimension != 4:
            raise ValueError("Observer must be 4-dimensional")
        self.maxbasis = maxBasis
        if rgbs is not None:
            self.rgbs = rgbs
        elif refs is not None and ref_wavelengths is not None:
            self.refs = refs
            self.ref_wavelengths = ref_wavelengths
        else: 
            raise ValueError("Either rgbs or refs and ref_wavelengths must be provided")
        self.point_cloud = point_cloud
        self.verbose = verbose

    
    def __get_corners(self):
        # center, then the 4 corners of the face
        list_corners = [[6, 11, 3, 1, 13], [5, 12, 2, 1, 11], [8, 2, 14, 11, 3], [10, 14, 4, 3, 13], [7, 4, 12, 13, 1], [9, 12, 4, 2, 14]]
        refs, maxbasispoints, rgbs, lines = self.maxbasis.getDiscreteRepresentation()
        points = transformToChromaticity(maxbasispoints)
        pts_corners = points[list_corners]
        rgb_corners = rgbs[list_corners]
        return pts_corners, rgb_corners

    def _sample_cube_map(self, satval=1.0, side_len=9):
        d = 6
        cube_pts, _ = self.__get_corners()
        all_directions = sampleCubeMapFaces(cube_pts[:, 1:], side_len) # get chromaticity coord of corners
        for j in range(d):
            all_directions[j] = all_directions[j] / np.repeat(np.expand_dims(np.linalg.norm(all_directions[j], axis=1), axis=1), repeats=3, axis=1) * satval # normalize them
        return all_directions
    
    def __find_closest_points(self, candidate_points, lumval, samples_per_point=25, radius_limit=0.5, lum_thresh=0.8, out_of_range_color=[0.75, 0.75, 0.75]):
        # for each point, find top samples_per_point closest points, and figure out which one is closest to the luminance value
        kdtree = KDTree(self.point_cloud)
        dd, ii = kdtree.query(candidate_points, samples_per_point, distance_upper_bound=radius_limit)
        dd, ii = dd.reshape(-1, samples_per_point), ii.reshape(-1, samples_per_point)
        final_idxs = []
        updated_dd = []
        final_rgbs = []
        for i in tqdm(range(len(ii)), disable=not self.verbose): # set of reflectances for each point, pick closeset
            idxs = [idx for idx in ii[i] if idx != self.point_cloud.shape[0]]
            dists = [d for d in dd[i] if d != np.inf]
            
            # if no points are found, set to dummy value
            if len(idxs) == 0: 
                final_idxs += [0]
                updated_dd += [np.inf]
                final_rgbs += [out_of_range_color]
                print(f"Point {i} has no close points")
                continue

            if hasattr(self, "rgbs"):
                rgb = self.rgbs[idxs]
            else:
                rgb = np.array([Spectra(np.concatenate([self.ref_wavelengths[:, np.newaxis], self.refs[idx][:, np.newaxis]], axis=1)).to_rgb() for idx in idxs])

            min_idx = min(range(len(rgb)), key=lambda j: abs(np.sum(rgb[j])-lumval))
            if abs(np.sum(rgb[min_idx])-lumval) > lum_thresh:
                final_idxs += [0] #dummy val
                updated_dd += [np.inf]
                final_rgbs += [out_of_range_color]
                print(f"Point {i} has no close points in luminance range")
                continue
            
            final_idxs += [idxs[min_idx]]
            updated_dd += [dists[min_idx]]
            final_rgbs += [rgb[min_idx]]
        return np.array(final_idxs), np.array(updated_dd), np.array(final_rgbs)
    
    def _find_closest_points(self, candidate_points, points, lmsq_radius_limit):
        kdtree = KDTree(points)
        dd, ii = kdtree.query(candidate_points, 1, distance_upper_bound=lmsq_radius_limit)
        return np.array(ii), np.array(dd)
    
    def _get_cubemap_samples_in_hering(self, lumval, satval, side_len):
        sphere_pts = self._sample_cube_map(satval, side_len).reshape(-1, 3)
        lumvals = np.repeat(lumval, sphere_pts.shape[0])
        candidate_points = np.hstack([lumvals[:, np.newaxis], sphere_pts])

        return candidate_points

    def _get_cubemap_samples_in_lmsq(self, lumval, satval, side_len):
        sphere_pts = self._sample_cube_map(satval, side_len).reshape(-1, 3)
        lumvals = np.repeat(lumval, sphere_pts.shape[0])
        candidate_points = np.hstack([lumvals[:, np.newaxis], sphere_pts])

        Hmatrix = getHeringMatrix(4)
        Tmat = np.linalg.inv(Hmatrix @ self.maxbasis.get_cone_to_maxbasis_transform())
        candidate_points_in_lmsq = (Tmat @ candidate_points.T).T
        return candidate_points_in_lmsq
    

    def get_cube_map(self, lumval, satval, side_len, radius_lim=0.025, method="hering"):
         # hering basis metric
        candidate_points_hering = self._get_cubemap_samples_in_hering(lumval, satval, side_len)
        HMatrix = getHeringMatrix(4)
        Tmat = self.maxbasis.get_cone_to_maxbasis_transform()
        hering_pts = (HMatrix @ Tmat @ self.point_cloud.T).T
            
        candidate_points_cone = self._get_cubemap_samples_in_lmsq(lumval, satval, side_len)

        if method == "hering":
            ii, dd = self._find_closest_points(candidate_points_hering, hering_pts, radius_lim)
        else:
            ii, dd =  self._find_closest_points(candidate_points_cone, self.point_cloud, radius_lim)
        
        cone_basis_pts =  np.array([self.point_cloud[i] if i != self.point_cloud.shape[0] else np.array([np.nan, np.nan, np.nan, np.nan]) for i in ii ])
        maxbasis_pts =  np.array([hering_pts[i] if i != self.point_cloud.shape[0] else np.array([np.nan, np.nan, np.nan, np.nan]) for i in ii ])

       
        if hasattr(self, "rgbs"):
            rgb = self.rgbs[ii]
        else:
            rgb = []
            for dist, idx in zip(dd, ii): 
                if idx == self.point_cloud.shape[0]: 
                    rgb +=[[0.75, 0.75, 0.75]]
                else:
                    rgb += [Spectra(np.concatenate([self.ref_wavelengths[:, np.newaxis], self.refs[idx][:, np.newaxis]], axis=1)).to_rgb()]
            rgb = np.array(rgb)

        return ii, dd, rgb, cone_basis_pts, maxbasis_pts, candidate_points_cone, candidate_points_hering

    def display_cube_map(self, lumval, satval, side_len):
        idxs, distances, rgb = self.get_cube_map(lumval, satval, side_len)
        fig, ax = plt.subplots(figsize=(6,4))
        plt.axis('off')
        plt.gca().set_aspect('equal')
        plt.tight_layout()

        self._display_cube_map(ax, rgb, side_len)
        plt.show()

    def _display_cube_map(self, ax, rgb, side_len):
        cube_left_corner_pts = np.array([[1, 2], [0, 1], [1, 1], [2, 1], [3, 1], [1, 0]])

        step = 1/side_len
        # sample in the center of the square of each sub square
        square = np.array([[i, j] for i in (np.arange(0, 1, step) + (1/2*step)) for j in np.arange(0, 1, step) + (1/2*step) ]).reshape(side_len, side_len, 2)
        cubemap = np.array([ x + square for x in cube_left_corner_pts])

        cm = cubemap.reshape(-1, 2)
        ax.scatter(cm[:, 0], cm[:, 1], c=rgb.reshape(-1, 3), s=70)


    def get_cubemap_percentages(self, perc, lumval, satval, side_len, method='hering'):
        # get the percentage of each face of the cube map
        idxs, distances, rgb, selected_conebasis, selected_maxbasis, candidate_conebasis_pts, candidate_maxbasis_pts = self.get_cube_map(lumval, satval, side_len, method=method)
        percentages =  np.array([perc[i] if i != perc.shape[0] else np.array([np.nan, np.nan, np.nan, np.nan, np.nan]) for i in idxs ])
        return percentages.reshape(6, side_len * side_len, perc.shape[1])

    def display_detailed_cubemap(self, lumval, satval, side_len, method='hering'):
        # sphere_pts = self._sample_cube_map(satval, side_len).reshape(-1, 3)
        # lmsq_sphere_pts = self._get_cubemap_samples_in_lmsq(lumval, satval, side_len)

        idxs, distances, rgb, selected_conebasis, selected_maxbasis, candidate_conebasis_pts, candidate_maxbasis_pts = self.get_cube_map(lumval, satval, side_len, method=method)
        fig, ax = plt.subplots(1, 1, figsize=(6, 6))
        ax.set_title("Cube Map", fontsize=10)
        # Cubemap Plot
        ax.axis('off')
        plt.gca().set_aspect('equal')
        plt.tight_layout()
        self._display_cube_map(ax, rgb.reshape(6, side_len * side_len, 3), side_len)
        plt.show()

        # Plots of the spectral reflectances
        fig = plt.figure(figsize=(12, 6))
        ax = fig.add_subplot(2, 2, 1, projection='3d')
        ax.set_title("Printer and Sphere Points in MaxBasis Chromaticity Space", fontsize=10)

        Tmat = self.maxbasis.get_cone_to_maxbasis_transform()
        maxbasis_pts = (Tmat @ self.point_cloud.T).T
        chrom_pts = transformToChromaticity(maxbasis_pts)
        plotTogether(ax, chrom_pts[::1000, :], candidate_maxbasis_pts[:, 1:])

        ax = fig.add_subplot(2, 2, 2, projection='3d')
        ax.set_title("Printer and Sphere Points in LQMS Chromaticity Space", fontsize=10)
        plotTogether(ax, transformToChromaticity(self.point_cloud[::1000, :]), transformToChromaticity(candidate_conebasis_pts))

        # reproject the sphere points back into the diagram to compare

        ax = fig.add_subplot(2, 2, 3, projection='3d')
        ax.set_title("Reprojected Selected Points in Metric Basis", fontsize=10)
        ax.scatter(candidate_maxbasis_pts[:, 1], candidate_maxbasis_pts[:, 2], candidate_maxbasis_pts[:, 3], s=70, c='r', alpha=0.1)
        selected_points = np.array([pt for pt in selected_maxbasis.reshape(-1, 4) if (pt != np.array([np.nan, np.nan, np.nan, np.nan])).all()])
        selected_rgbs = np.array([rgb for rgb, pt in zip(rgb.reshape(-1, 3), selected_maxbasis.reshape(-1, 4)) if (pt != np.array([np.nan, np.nan, np.nan, np.nan])).all()])
        ax.scatter(selected_points[:, 1], selected_points[:, 2], selected_points[:, 3], c=selected_rgbs, s=70)

        ax = fig.add_subplot(2, 2, 4, projection='3d')
        ax.set_title("Reprojected Selected Points in Metric Basis", fontsize=10)
        cand_pts = transformToChromaticity(candidate_conebasis_pts)
        ax.scatter(cand_pts[:, 0], cand_pts[:,  1], cand_pts[:, 2], s=70, c='r', alpha=0.1)
        selected_points = transformToChromaticity(np.array([pt for pt in selected_conebasis.reshape(-1, 4) if (pt != np.array([np.nan, np.nan, np.nan, np.nan])).all()]))
        selected_rgbs = np.array([rgb for rgb, pt in zip(rgb.reshape(-1, 3), selected_conebasis.reshape(-1, 4)) if (pt != np.array([np.nan, np.nan, np.nan, np.nan])).all()])
        ax.scatter(selected_points[:, 0], selected_points[:, 1], selected_points[:, 2], c=selected_rgbs, s=70)

        plt.show()
        
        # selected_refs = self.refs[idxs]
        cubemap_rgb = rgb.reshape(6, side_len* side_len, 3)
        fig, ax = plt.subplots(3, 6, figsize=(12, 6))
        for k, tb in enumerate([0, -1]):
            for i in range(3):
                for j in range(3):
                    idx = idxs.reshape(6, side_len * side_len)[tb][i*3+ 3*j]
                    if  idx == self.refs.shape[0]:
                        ax[i, j + 3 *k].set_title("No Close Points")
                    else:
                        ax[i, j + 3 *k].plot(self.ref_wavelengths, self.refs[idx], c = cubemap_rgb[tb][i*3+ 3*j])
                        ax[i, j + 3 *k].set_ylim([0, 1])
            fig.tight_layout()
        
        plt.show()
        return selected_maxbasis, idxs





              
        
