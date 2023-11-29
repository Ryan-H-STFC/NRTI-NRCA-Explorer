from __future__ import annotations
import numpy as np
from numpy import ndarray
from os import path
import pandas
from pandas import DataFrame

from element.PeakDetection import PeakDetector
from helpers.getSpacedElements import getSpacedElements
from helpers.fitBoxes import fitBoxes
from helpers.getIndex import getIndex
from helpers.integration import integrate_simps
from helpers.nearestNumber import nearestnumber
from helpers.smooth import smooth

dataFilepath = f"{path.dirname(path.dirname(__file__))}\\data\\Graph Data\\"
peakLimitFilepath = f"{path.dirname(path.dirname(__file__))}\\data\\Peak Limit Information\\"


class ElementData:
    """
    Data class ElementData used to create a structure for each unique element selection and its data. along with
    altered python dunder functions utilised throughout the program.
    """

    name: str
    numPeaks: int
    maxPeaks: int = 50
    tableData: DataFrame
    graphData: DataFrame
    distributions: dict
    defaultDist: dict
    graphColour: tuple

    annotations: list
    annotationsOrder: dict
    threshold: float = 100.0

    maxima: ndarray = None
    minima: ndarray = None

    maxPeakLimitsX: dict
    maxPeakLimitsY: dict
    minPeakLimitsY: dict
    minPeakLimitsX: dict

    isAnnotationsDrawn: bool = False
    isAnnotationsHidden: bool = False
    isCompound: bool = False
    isDistAltered: bool = False
    isGraphDrawn: bool = False
    isGraphHidden: bool = False
    isGraphUpdating: bool = False
    isImported: bool = False
    isMaxDrawn: bool = False
    isMinDrawn: bool = False
    isToF: bool = False

    def __init__(self,
                 name: str,
                 numPeaks: int,
                 tableData: DataFrame,
                 graphData: DataFrame,
                 graphColour: tuple,
                 isToF: bool,
                 distributions: dict,
                 defaultDist: dict,
                 isCompound: bool = False,
                 isAnnotationsHidden: bool = False,
                 threshold: float = 100,
                 isImported: bool = False) -> None:

        self.name = name
        self.numPeaks = numPeaks
        self.isToF = isToF
        self.distributions = distributions
        self.defaultDist = defaultDist
        self.isCompound = isCompound
        self.annotations = []
        self.annotationsOrder = {}
        self.maxPeakLimitsX = {}
        self.maxPeakLimitsY = {}

        self.isAnnotationsHidden = isAnnotationsHidden
        self.threshold = threshold
        self.isImported = isImported
        pd = PeakDetector()

        self.tableData = tableData

        if self.tableData is None:
            self.tableData = DataFrame()

        self.graphData = graphData
        if self.defaultDist != self.distributions:
            self.isDistAltered = True
            self.onDistChange()
            self.UpdatePeaks()

        if self.graphData is None:
            self.graphData = DataFrame()

        self.graphColour = graphColour

        length = 23.404 if self.name[-1] == "t" else 22.804

        if self.isToF and not self.graphData.empty:
            graphData[0] = self.energyToTOF(graphData[0], length=length)
            graphData.sort_values(0, ignore_index=True, inplace=True)
        try:
            if not self.graphData.empty and not self.isDistAltered:
                self.maxima = np.array(pd.maxima(graphData, threshold))

                self.minima = np.array(pd.minima(graphData))
        except AttributeError:
            # Case when creating compounds, -> requires use of setGraphDataFromDist before plotting.
            pass
        try:
            name = self.name[8:] if 'element' in self.name else self.name
            limits = pandas.read_csv(f"{peakLimitFilepath}{name}.csv", names=['left', 'right'])
            if self.isToF:
                limits['left'] = self.energyToTOF(limits['left'], length)
                limits['right'] = self.energyToTOF(limits['right'], length)
                limits['left'], limits['right'] = limits['right'], limits['left']

            for max in self.maxima[0]:
                lim = limits[(limits['left'] < max) & (limits['right'] > max)]
                if lim.empty:
                    continue
                self.maxPeakLimitsX[max] = (lim['left'].iloc[0], lim['right'].iloc[0])
                leftLimit = nearestnumber(graphData[0], lim['left'].iloc[0])
                rightLimit = nearestnumber(graphData[0], lim['right'].iloc[0])
                self.maxPeakLimitsY[max] = (graphData[graphData[0] == leftLimit].iloc[0, 1],
                                            graphData[graphData[0] == rightLimit].iloc[0, 1])

        except ValueError:
            # Catches invalid maximas produced by scipy.signal.find_peaks
            pass
        except FileNotFoundError:
            if self.maxima is not None:
                self.definePeaks()
                self.recalculatePeakData()

        if self.numPeaks is None:
            self.numPeaks = None if self.maxima is None else len(self.maxima[0])

    def __eq__(self, other) -> bool:
        if isinstance(other, ElementData):
            ck = self.name == other.name and self.isToF == other.isToF and self.graphData == other.graphData
            return ck
        return False

    def __ne__(self, other) -> bool:
        if isinstance(other, ElementData):
            return self.name != other.name or self.isToF != other.isToF or self.graphData != other.graphData
        return True

    def energyToTOF(self, xData: float | list[float], length: float | None = None) -> list[float]:
        """
        Maps all X Values from energy to TOF

        Args:
            - ``xData`` (list[float]): List of the substances x-coords of its graph data

            - ``length`` (float, optional): Constant value associated to whether the element data is with repsect to
                                          n-g or n-tot


        Returns:
            list[float]: Mapped x-coords
        """
        if length is None:
            length = 23.404 if self.name[-1] == "t" else 22.804
        neutronMass = float(1.68e-27)
        electronCharge = float(1.60e-19)

        tofX = list(
            map(
                lambda x: length * 1e6 * (0.5 * neutronMass / (x * electronCharge)) ** 0.5,
                xData
            )
        )
        return tofX

    def e2TOF(self, xData: float, length: float | None = None) -> list[float]:
        """
        Maps all X Values from energy to TOF

        Args:
            - ``xData`` (float): x-Value.

            - ``length`` (float, optional): Constant value associated to whether the element data is with repsect to
                                          n-g or n-tot

        Returns:
            float: Mapped x-coords
        """
        if length is None:
            length = 23.404 if self.name[-1] == "t" else 22.804
        neutronMass = float(1.68e-27)
        electronCharge = float(1.60e-19)

        return length * 1e6 * (0.5 * neutronMass / (xData * electronCharge)) ** 0.5

    def onDistChange(self) -> None:
        """
        ``onDistChange`` Will retrieve an elements the corresponding isotopes graphData appling the weights specified in
        the menu.
        """
        if not self.isDistAltered and not ('element' in self.name or 'compound' in self.name):
            return

        self.weightedIsoGraphData = {name: pandas.read_csv(
            f"""{dataFilepath}{'_'.join(name.split('_')[0:-1])}_{
            self.name.split('_')[-1]}.csv""",
            names=['x', 'y'],
            header=None) * [1, dist]
            for name, dist in self.distributions.items() if dist != 0}
        self.setGraphDataFromDist(self.weightedIsoGraphData.values())

    def setGraphDataFromDist(self, weightedGraphData: list[DataFrame]) -> None:
        """
        ``setGraphDataFromDist`` Given a list of graphData return a sum of its merged date.
        By merging the x-data either retrieve or linearly interplote for each graphData in the list to produce a y-value
        for the new x-domain. Then sum the resulting y-values inplace and setting the graphData of the instance.


        Args:
            ``weightedGraphData`` (list[DataFrame]): List of graph data for each element or isotope to be summed.
        """

        graphDataX = []
        peakD = PeakDetector()
        for graphData in weightedGraphData:

            graphDataX += peakD.maxima(graphData, 0)[0] if self.maxima is None else list(self.maxima[0])
            graphDataX += peakD.minima(graphData)[0] if self.minima is None else list(self.minima[0])
            graphDataX = list(getSpacedElements(np.array(graphData.iloc[:, 0]),
                                                graphData.shape[0] // 2)) + graphDataX
        self.graphDataX = np.unique(graphDataX)

        isoY = np.zeros(shape=(len(weightedGraphData), self.graphDataX.shape[0]))

        # coreCount = cpu_count()
        # p = Pool(processes=coreCount)
        for i, graphData in enumerate(weightedGraphData):
            isoY[i] = np.interp(self.graphDataX, graphData.iloc[:, 0], graphData.iloc[:, 1])
        # isoY = np.array(p.map(self._getGraphDataFromDist, list(weightedGraphData.values()), coreCount))
        # p.close()
        # p.join()
        self.graphData = pandas.DataFrame(sorted(zip(self.graphDataX, np.sum(isoY, axis=0))))

    def UpdatePeaks(self) -> None:
        """
        ``UpdatePeaks`` recalulates maxima coordinates and updates associated variables.
        Used when threshold values have been altered.
        """
        peakD = PeakDetector()
        self.maxima = np.array(peakD.maxima(self.graphData, self.threshold))
        self.numPeaks = len(self.maxima[0])
        self.definePeaks()

        self.minima = np.array(peakD.minima(self.graphData))

    def HideAnnotations(self, globalHide: bool = False) -> None:
        """
        HideAnnotations will only hide if 'Hide Peak Label' is checked, or the graph is hidden,
        otherwise it will show the annotation.

        Args:
            globalHide (bool, optional): Wheher or not the 'Hide Peak Label' is checked or not. Defaults to False.
        """
        if self.annotations == []:
            return

        boolCheck = not (globalHide or self.isGraphHidden)
        for point in self.annotations:
            point.set_visible(boolCheck)
        self.isAnnotationsHidden = boolCheck

    def OrderAnnotations(self, byIntegral: bool = True) -> None:
        """
        ``OrderAnnotations`` alters the rank value assoicated with each peak in the annotations dictionary
        either ranked by integral or by peak width

        Args:
            ``byIntegral`` (bool, optional): Sorted by Integral (True) else by Peak Width (False). Defaults to True.
        """
        self.annotationsOrder.clear()
        if self.numPeaks == 0:
            return
        if self.isImported:
            return

        if self.tableData[1:].empty:
            return

        rankCol = "Rank by Integral" if byIntegral else "Rank by Peak Width"
        xCol = "TOF (us)" if self.isToF else "Energy (eV)"
        yCol = "Peak Height"
        for i in range(self.numPeaks):
            if byIntegral:
                row = self.tableData[1:].loc[
                    (self.tableData[rankCol][1:] == i)
                ]
            else:
                row = self.tableData[1:].loc[
                    (self.tableData[rankCol][1:] == f'({i})')
                ]

            if row.empty:
                continue
            else:
                max_x = nearestnumber(self.maxima[0], row[xCol].iloc[0])
                max_y = nearestnumber(self.maxima[1], row[yCol].iloc[0])
            self.annotationsOrder[i] = (max_x, max_y)

    def PeakIntegral(self, leftLimit: float, rightLimit: float) -> float:
        if "element" in self.name:
            isoGraphData = {name: pandas.read_csv(f"{dataFilepath}{name}_{self.name.split('_')[-1]}.csv",
                                                  names=['x', 'y'],
                                                  header=None)
                            for name, dist in self.distributions.items() if dist != 0}

            integrals = []
            for name, graphData in isoGraphData.items():
                # regionGraphData = graphData[(graphData['x'] >= leftLimit) & (graphData['x'] <= rightLimit)]
                integrals.append(integrate_simps(graphData, leftLimit, rightLimit) * self.distributions[name])

            return sum(integrals)
        else:
            # regionGraphData = self.graphData[(graphData['x'] >= leftLimit) & (graphData['x'] <= rightLimit)]
            return integrate_simps(self.graphData, leftLimit, rightLimit)

    def definePeaks(self):
        """
        ``definePeaks``
        ---------------
        Calculates the limits of integration for peaks.

        Credits go to Ivan Alsina Ferrer - https://github.com/ialsina/NRCA-Spectra/tree/main

        Peak Limit Algorithm used with all pre-existing datasets, now reimplented for use in the GUI.
        """
        params = {
            # Maximum value prange can get.
            'prangemax': 500,
            # Maximum allowed slope (abolute value) at outermost left side of spectra.
            # i.e. starting from left, everything will be set to 0 until the (unsigned) slope reaches this value.
            'maxleftslope': 3000,
            # Maximum allowed slope outside the peaks, as in, far away from them.
            'maxouterslope': 10,
            # Peak edges is set when its slope has fallen down to this fraction of the one nearby the peak summit.
            'slopedrop': .1,
            # Density of boxes (box/b) for slope computation.
            'dboxes': 100,
            # Smoothing iterations on slope derivative for computations.
            'itersmooth': 1,
            # Smoothing iterations on sample peak detection.
            'itersmoothsamp': 0,
            # Strip-peaks iterations for background fitting in sample imports.
            'iterspeaks': 4,
            # Number of coefficients in smaple background fitting, i.e., polynomial order + 1s
            'fitting_coeff': 8,
            # Default tolerance value (us) for finding nearby peaks in pmatch function.
            'max_match': 3.5,
        }

        derivative = np.array(
            [(self.graphData.iloc[i + 1, 1] - self.graphData.iloc[i, 1]
              ) / (self.graphData.iloc[i + 1, 0] - self.graphData.iloc[i, 0])
             for i in range(self.graphData.shape[0] - 1)])

        indexPosDer = getIndex(np.int32(derivative < 0), 0)
        target = np.hstack((np.ones((indexPosDer)), np.zeros((np.size(derivative) - indexPosDer))))
        derivative = derivative * (np.int64(np.abs(derivative) < params['maxleftslope']) * target + (1 - target))
        smoothDer = smooth(derivative, params['itersmooth'])

        maxIndexes = [self.graphData[self.graphData[0] == max].index[0] for max in self.maxima[0]]
        for i, max in enumerate(self.maxima[0]):
            # Number of points at the left of the current peak
            nleft = maxIndexes[i]
            # Number of points at the right of the current peak
            nright = np.shape(self.graphData)[0] - nleft - 1
            if np.size(self.maxima > 1):
                if i == 0 or i == np.size(self.maxima[0]) - 1:
                    prange = min(params['prangemax'], nleft, nright)
                else:
                    indexPrev = maxIndexes[i - 1]
                    indexNext = maxIndexes[i + 1]
                    prange = min(params['prangemax'], indexNext - indexPrev, nleft, nright)
            elif np.size(self.maxima) == 1:
                prange = min(params['prangemax'], nleft, nright)
            else:
                prange = 0

            maxIndex = maxIndexes[i]
            derRegion = smoothDer[maxIndex - prange: maxIndex + prange + 1]
            for i in range(1, 10):
                fit, boxwidth = fitBoxes(derRegion, params['dboxes'] * i)
                temp1, temp2 = np.unique(fit, return_counts=True)
                if not (temp2 == 1).all():
                    break
            outerslope = temp1[np.argmax(temp2)]
            if abs(outerslope) > params['maxouterslope']:
                outerslope = 0
            limsX = []
            limsY = []
            for sign in [-1, 1]:
                decreasing, increasing, lock = False, False, False
                derMax = None
                for i in range(maxIndex, maxIndex + sign * (prange + 1), sign):
                    decreasing = smoothDer[i + sign] < smoothDer[i]
                    increasing = smoothDer[i + sign] > smoothDer[i]
                    if not lock:
                        if (decreasing if sign == -1 else increasing):
                            lock = True
                            derMax = smoothDer[i]
                            if derMax == outerslope:
                                raise Exception('Non-standing slope', prange)
                    if lock:
                        if abs((derivative[i] - outerslope) / (derMax - outerslope)) <= params['slopedrop']:
                            limsX.append(self.graphData.iloc[i, 0])
                            limsY.append(self.graphData.iloc[i, 1])
                            break
                        if smoothDer[i + sign] * smoothDer[i] <= 0:
                            limsX.append(self.graphData.iloc[i, 0])
                            limsY.append(self.graphData.iloc[i, 1])
                            break
            try:
                self.maxPeakLimitsX[max] = (limsX[0], limsX[1])
                self.maxPeakLimitsY[max] = (limsY[0], limsY[1])
            except IndexError:
                pass

    def recalculatePeakData(self):

        integrals = {max: self.PeakIntegral(self.maxPeakLimitsX[max][0], self.maxPeakLimitsX[max][1])
                     for max in self.maxima[0]}
        integralRanks = {max: i for i, max in enumerate(dict(
            sorted(integrals.items(), key=lambda item: item[1], reverse=True)).keys())}

        peakHeightRank = {max: i for i, max in enumerate(sorted(self.maxima[1], key=lambda item: item, reverse=True))}

        peakWidth = {max: self.maxPeakLimitsX[max][1] - self.maxPeakLimitsX[max][0] for max in self.maxima[0]}

        peakWidthRank = {max: i for i, max in enumerate(dict(
            sorted(peakWidth.items(), key=lambda item: item[1], reverse=True)).keys())}

        tableDataTemp = [
            [
                integralRanks[maxCoords[0]],
                round(maxCoords[0], 4),
                f"({np.where(self.maxima[0] == maxCoords[0])[0][0]})",
                round(self.e2TOF(maxCoords[0]), 4),
                round(integrals[maxCoords[0]], 4),
                round(peakWidth[maxCoords[0]], 4),
                peakWidthRank[maxCoords[0]],
                round(maxCoords[1], 4),
                peakHeightRank[maxCoords[1]],
                None
            ]
            for maxCoords in self.maxima.T]

        tableData = pandas.DataFrame(tableDataTemp,
                                     columns=[
                                         "Rank by Integral",
                                         "Energy (eV)",
                                         "Rank by Energy",
                                         "TOF (us)",
                                         "Integral",
                                         "Peak Width",
                                         "Rank by Peak Width",
                                         "Peak Height",
                                         "Rank by Peak Height",
                                         "Relevant Isotope"
                                     ])
        self.tableData = tableData.sort_values('Rank by Integral')
        self.tableData.loc[-1] = [self.name, *[""] * 9]
        self.tableData.index += 1
        self.tableData.sort_index(inplace=True)
