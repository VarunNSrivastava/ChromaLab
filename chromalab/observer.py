from importlib import resources
from itertools import combinations
from typing import List, Union, Optional

import numpy as np
import numpy.typing as npt
import pandas as pd

from .spectra import Spectra


def BaylorNomogram(wls, lambdaMax: int):
    """
    Baylor, Nunn, and Schnapf, 1987.
    """
    # These are the coefficients for the polynomial approximation.
    aN = np.array([-5.2734, -87.403, 1228.4, -3346.3, -5070.3, 30881, -31607])

    wlsum = wls / 1000.0
    wlsVec = np.log10((1.0 / wlsum) * lambdaMax / 561)
    logS = aN[0] + aN[1] * wlsVec + aN[2] * wlsVec ** 2 + aN[3] * wlsVec ** 3 + \
           aN[4] * wlsVec ** 4 + aN[5] * wlsVec ** 5 + aN[6] * wlsVec ** 6
    T = 10 ** logS
    return Cone(data=T.T, wavelengths=wls, quantal=True)


def GovardovskiiNomogram(S, lambdaMax):
    """
    Victor I. Govardovskii et al., 2000.
    """
    # Valid range of wavelength for A1-based visual pigments
    Lmin, Lmax = 330, 700

    # Valid range of lambdaMax value
    lmaxLow, lmaxHigh = 350, 600

    # Alpha-band parameters
    A, B, C = 69.7, 28, -14.9
    D = 0.674
    b, c = 0.922, 1.104

    # Beta-band parameters
    Abeta = 0.26

    # Assuming S is directly the wavelengths array
    wls = np.array(S)

    nWls = len(wls)
    T_absorbance = np.zeros((1, nWls))  # nT is assumed to be 1 based on user note

    if lmaxLow < lambdaMax < lmaxHigh:
        # alpha-band polynomial
        a = 0.8795 + 0.0459 * np.exp(-(lambdaMax - 300) ** 2 / 11940)

        x = lambdaMax / wls
        midStep1 = np.exp(np.array([A, B, C]) * np.array([a, b, c]) - x[:, None] * np.array([A, B, C]))
        midStep2 = np.sum(midStep1, axis=1) + D

        S_x = 1 / midStep2

        # Beta-band polynomial
        bbeta = -40.5 + 0.195 * lambdaMax
        lambdaMaxbeta = 189 + 0.315 * lambdaMax

        midStep1 = -((wls - lambdaMaxbeta) / bbeta) ** 2
        S_beta = Abeta * np.exp(midStep1)

        # alpha band and beta band together
        T_absorbance[0, :] = S_x + S_beta

        # Zero sensitivity outside valid range
        T_absorbance[0, wls < Lmin] = 0
        T_absorbance[0, wls > Lmax] = 0
    else:
        raise ValueError(f'Lambda Max {lambdaMax} not in range of nomogram')

    return Cone(data=np.clip(T_absorbance.T, 0, 1), wavelengths=wls, quantal=True)


def LambNomogram(wls, lambdaMax):
    """
    Lamb, 1995.
    """
    # Coefficients for Equation 2
    a, b, c = 70, 28.5, -14.1
    A, B, C, D = 0.880, 0.924, 1.104, 0.655

    wlarg = lambdaMax / wls
    T = 1 / (np.exp(a * (A - wlarg)) + np.exp(b * (B - wlarg)) +
             np.exp(c * (C - wlarg)) + D)
    T = T / max(T)  # Normalize the sensitivity to peak at 1

    return Cone(data=T, wavelengths=wls)


def StockmanSharpeNomogram(wls, lambdaMax):
    """
    Stockman and Sharpe nomogram.
    """
    # Polynomial coefficients
    a = -188862.970810906644
    b = 90228.966712600282
    c = -2483.531554344362
    d = -6675.007923501414
    e = 1813.525992411163
    f = -215.177888526334
    g = 12.487558618387
    h = -0.289541500599

    # Prepare the wavelengths normalization
    logWlsNorm = np.log10(wls) - np.log10(lambdaMax / 558)

    # Compute log optical density
    logDensity = (a + b * logWlsNorm ** 2 + c * logWlsNorm ** 4 +
                  d * logWlsNorm ** 6 + e * logWlsNorm ** 8 +
                  f * logWlsNorm ** 10 + g * logWlsNorm ** 12 +
                  h * logWlsNorm ** 14)

    # Convert log10 absorbance to absorbance
    T_absorbance = 10 ** logDensity

    return Cone(data=T_absorbance, wavelengths=wls, quantal=True)


def NeitzNomogram(wls, lambda_max=559):
    # Carroll, McMahon, Neitz, & Neitz (2000)

    wls = wls.astype(np.float32)

    A = 0.417050601
    B = 0.002072146
    C = 0.000163888
    D = -1.922880605
    E = -16.05774461
    F = 0.001575426
    G = 5.11376e-05
    H = 0.00157981
    I = 6.58428e-05
    J = 6.68402e-05
    K = 0.002310442
    L = 7.31313e-05
    M = 1.86269e-05
    N = 0.002008124
    O = 5.40717e-05
    P = 5.14736e-06
    Q = 0.001455413
    R = 4.217640000e-05
    S = 4.800000000e-06
    T = 0.001809022
    U = 3.86677000e-05
    V = 2.99000000e-05
    W = 0.001757315
    X = 1.47344000e-05
    Y = 1.51000000e-05

    A2 = (np.log10(1.00000000 / lambda_max) - np.log10(1.00000000 / 558.5))
    vector = np.log10(np.reciprocal(wls))
    const = 1 / np.sqrt(2 * np.pi)

    ex_temp1 = np.log10(-E + E * np.tanh(-((10 ** (vector - A2)) - F) / G)) + D
    ex_temp2 = A * np.tanh(-(((10 ** (vector - A2))) - B) / C)
    ex_temp3 = -(J / I * (const * np.exp(-0.5 * (((10 ** (vector - A2)) - H) / I) ** 2)))
    ex_temp4 = -(M / L * (const * np.exp(-0.5 * (((10 ** (vector - A2)) - K) / L) ** 2)))
    ex_temp5 = -(P / O * (const * np.exp(-0.5 * (((10 ** (vector - A2)) - N) / O) ** 2)))
    ex_temp6 = (S / R * (const * np.exp(-0.5 * (((10 ** (vector - A2)) - Q) / R) ** 2)))
    ex_temp7 = ((V / U * (const * np.exp(-0.5 * (((10 ** (vector - A2)) - T) / U) ** 2))) / 10)
    ex_temp8 = ((Y / X * (const * np.exp(-0.5 * (((10 ** (vector - A2)) - W) / X) ** 2))) / 100)
    ex_temp = ex_temp1 + ex_temp2 + ex_temp3 + ex_temp4 + ex_temp5 + ex_temp6 + ex_temp7 + ex_temp8

    return Cone(data=np.clip(10 ** ex_temp, 0, 1), wavelengths=wls, quantal=True)


def load_csv(name) -> Spectra:
    with resources.path("chromalab.cones", name) as data_path:
        return Spectra(np.array(pd.read_csv(data_path, header=None)), normalized=False)


class Cone(Spectra):
    with resources.path("chromalab.cones", "ss2deg_10lin.csv") as data_path:
        ss_data = pd.read_csv(data_path, header=None).iloc[:-130, :]
    lens_absorption = load_csv("lensss_1.csv")
    macular_absorption = load_csv("macss_1.csv")
    templates = {
        "neitz": NeitzNomogram,
        "stockman": StockmanSharpeNomogram,
        "baylor": BaylorNomogram,
        "govardovskii": GovardovskiiNomogram,
        "lamb": LambNomogram
    }

    def __init__(self, array: Optional[Union[Spectra, npt.NDArray]] = None,
                 wavelengths: Optional[npt.NDArray] = None, data: Optional[npt.NDArray] = None,
                 quantal=False, **kwargs):
        self.quantal = quantal
        if isinstance(array, Spectra):
            super().__init__(**array.__dict__, **kwargs)
        else:
            super().__init__(array=array, wavelengths=wavelengths, data=data, **kwargs)

    def observe(self, spectra: Spectra, illuminant: Spectra):
        return np.divide(np.dot(self.data, spectra.data), np.dot(self.data, illuminant.data))

    def as_quantal(self):
        if self.quantal:
            return self
        log_data = np.log(self.data) - np.log(self.wavelengths)
        quantal_data = np.exp(log_data - np.max(log_data))
        attrs = self.__dict__.copy()
        attrs["data"] = quantal_data
        attrs["quantal"] = True
        return self.__class__(**attrs)

    def as_energy(self):
        if not self.quantal:
            return self
        log_data = np.log(self.wavelengths) + np.log(self.data)
        energy_data = np.exp(log_data - np.max(log_data))

        attrs = self.__dict__.copy()
        attrs["data"] = energy_data
        attrs["quantal"] = False
        return self.__class__(**attrs)

    def with_od(self, od):
        if not self.quantal:
            return self.as_quantal().with_od(od).as_energy()
        od_data = np.divide(1 - np.exp(np.log(10) * -od * self.data), 1 - (10 ** -od))
        attrs = self.__dict__.copy()
        attrs["data"] = od_data
        return self.__class__(**attrs)

    def with_preceptoral(self, od=0.35, lens=1, macular=1):
        # There are other lens and macular pigment data sources,
        # which can be found in the cones/ subfolder.
        if not self.quantal:
            return self.as_quantal().with_preceptoral(od, lens, macular)
        lens_spectra = lens * Cone.lens_absorption.interpolate_values(self.wavelengths)
        macular_spectra = macular * Cone.macular_absorption.interpolate_values(self.wavelengths)
        denom = (10 ** (lens_spectra + macular_spectra))
        C_r = self.with_od(od)
        return (~(C_r / denom)).as_energy()

    @staticmethod
    def cone(peak, template="govardovskii", od=0.35, wavelengths=None):
        # TODO: support L, M, S, Q peak, besides numerical
        # TODO: want to add eccentricity and/or macular, lens control
        if not isinstance(peak, (int, float)):
            raise ValueError("Currently only numerical peaks are supported.")
        if wavelengths is None:
            wavelengths = np.arange(400, 701, 1)
        if template not in Cone.templates:
            raise ValueError(f"Choose a template from {Cone.templates.keys()}")
        return Cone.templates[template](wavelengths, peak).with_preceptoral(od=od)

    @staticmethod
    def l_cone(wavelengths=None, template=None):
        if template is None:
            reflectances = Cone.ss_data.iloc[:, [0, 1]].to_numpy()
            return Cone(reflectances).interpolate_values(wavelengths)
        return Cone.cone(559, template=template, od=0.35, wavelengths=wavelengths)

    @staticmethod
    def m_cone(wavelengths=None, template=None):
        if template is None:
            reflectances = Cone.ss_data.iloc[:, [0, 2]].to_numpy()
            return Cone(reflectances).interpolate_values(wavelengths)
        return Cone.cone(530, template=template, od=0.35, wavelengths=wavelengths)

    @staticmethod
    def s_cone(wavelengths=None, template=None):
        if template is None:
            reflectances = Cone.ss_data.iloc[:, [0, 3]].dropna().to_numpy()
            return Cone(reflectances).interpolate_values(wavelengths)
        # http://www.cvrl.org/database/text/intros/introod.htm
        # "There are no good estimates of pigment optical densities for the S-cones."
        return Cone.cone(419, template=template, od=0.5, wavelengths=wavelengths)

    @staticmethod
    def q_cone(wavelengths=None, template="govardovskii"):
        return Cone.cone(547, template=template, od=0.35, wavelengths=wavelengths)


def get_m_transitions(m, wavelengths, both_types=True):
    all_transitions = []
    for combination in combinations(range(len(wavelengths)), m):
        arr = np.zeros_like(wavelengths, dtype=int)
        for index in combination:
            arr[index:] = 1 - arr[index]
        all_transitions.append(arr)
        if both_types:
            all_transitions.append(1 - arr)

    return all_transitions


class Observer:
    def __init__(self, sensors: List[Spectra], illuminant: Optional[Spectra] = None, min_transition_size: int = 10):
        self.dimension = len(sensors)
        self.sensors = sensors

        total_wavelengths = np.unique(np.concatenate([sensor.wavelengths for sensor in sensors]))
        self.wavelengths = total_wavelengths

        self.sensor_matrix = self.get_sensor_matrix(total_wavelengths)
        if illuminant is not None:
            illuminant = illuminant.interpolate_values(self.wavelengths).data
        else:
            illuminant = np.ones_like(self.wavelengths)

        self.illuminant = illuminant
        self.min_transition_size = min_transition_size

    @staticmethod
    def trichromat(wavelengths=None, illuminant=None):
        l_cone = Cone.l_cone(wavelengths)
        m_cone = Cone.m_cone(wavelengths)
        s_cone = Cone.s_cone(wavelengths)
        return Observer([s_cone, m_cone, l_cone], illuminant=illuminant)

    @staticmethod
    def tetrachromat(wavelengths=None, illuminant=None):
        l_cone = Cone.l_cone(wavelengths)
        q_cone = Cone.q_cone(wavelengths)
        m_cone = Cone.m_cone(wavelengths)
        s_cone = Cone.s_cone(wavelengths)
        return Observer([s_cone, m_cone, q_cone, l_cone], illuminant=illuminant)

    def get_whitepoint(self, wavelengths: Optional[npt.NDArray] = None):
        sensor_matrix = self.get_sensor_matrix(wavelengths)

        return np.matmul(sensor_matrix, self.illuminant)

    def get_sensor_matrix(self, wavelengths: Optional[npt.NDArray] = None):
        """
        Get sensor matrix as specific wavelengths
        """
        if wavelengths is None:
            return self.sensor_matrix
        # assert wavelengths is 1d etc
        sensor_matrix = np.zeros((self.dimension, wavelengths.shape[0]))
        for i, sensor in enumerate(self.sensors):
            for j, wavelength in enumerate(wavelengths):
                sensor_matrix[i, j] = sensor.interpolated_value(wavelength)

        return sensor_matrix

    def observe(self, data: Union[npt.NDArray, Spectra]):
        """
        Either pass in a Spectra of light to observe or data that agrees with self.wavelengths.
        """
        if isinstance(data, Spectra):
            if np.array_equal(data.wavelengths, self.wavelengths):
                data = data.data
            else:
                # have to interpolate
                interp_color = []
                for wavelength in self.wavelengths:
                    interp_color.append(data.interpolated_value(wavelength))
                data = np.array(interp_color)
        else:
            assert data.size == self.wavelengths.size, f"Data shape {data.shape} must match wavelengths shape {self.wavelengths.shape}"

        observed_color = np.matmul(self.sensor_matrix, data * self.illuminant)
        whitepoint = np.matmul(self.sensor_matrix, self.illuminant)

        return np.divide(observed_color, whitepoint)

    def dist(self, color1: Union[npt.NDArray, Spectra], color2: Union[npt.NDArray, Spectra]):
        return np.linalg.norm(self.observe(color1) - self.observe(color2))

    def get_transitions(self) -> List[npt.NDArray]:
        transitions = []

        num_wavelengths = self.sensor_matrix.shape[1]
        indices = list(range(num_wavelengths // self.min_transition_size))

        # append black and white spectra at the start
        transitions.append(np.zeros(num_wavelengths))
        transitions.append(np.ones(num_wavelengths))

        for selected_indices in combinations(indices, 2 * (self.dimension - 1)):
            intervals = [(selected_indices[i], selected_indices[i + 1]) for i in range(0, len(selected_indices), 2)]

            transition = np.zeros(num_wavelengths)
            for start, end in intervals:
                transition[self.min_transition_size * start:self.min_transition_size * end] = 1

            transitions.append(transition)

        return transitions

    def get_transition(self, index: int) -> npt.NDArray:
        # todo: combinatorial approach instead of this ridiculousness
        return list(self.get_transitions())[index]

    def get_full_colors(self) -> npt.NDArray:
        transitions = self.get_transitions()
        transitions_matrix = np.array(transitions).T

        colors = np.matmul(self.sensor_matrix, transitions_matrix)
        return np.divide(colors, self.whitepoint.reshape((-1, 1)))


def gaussian(x, A, mu, sigma):
    return A * np.exp(-(x - mu) ** 2 / (2 * sigma ** 2))
