# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import numpy as np
import numba as nb
import pandas as pd
from scipy.sparse import csc_matrix
from typing import List, Union, Any
from GridCalEngine.basic_structures import IntVec, StrMat, StrVec, Vec, Mat
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit
from GridCalEngine.Devices import ContingencyGroup
from GridCalEngine.Simulations.LinearFactors.linear_analysis import LinearMultiContingency
from GridCalEngine.Simulations.ContingencyAnalysis.Methods.srap import BusesForSrap
from GridCalEngine.Utils.Sparse.csc_numba import get_sparse_array_numba


@nb.njit(cache=True)
def get_ptdf_comp_numba(data, indices, indptr, PTDF, m, bd_indices):
    """
    This computes the compensatd PTDF for a single branch
    PTDFc = MLODF[m, βδ] x PTDF[βδ, :] + PTDF[m, :]
    :param data: MLODF[:, βδ].data
    :param indices: MLODF[:, βδ].indices
    :param indptr: MLODF[:, βδ].indptr
    :param PTDF: Full PTDF matrix
    :param m: intex of the monitored branch
    :param bd_indices: indices of the failed branches
    :return:
    """
    # Perform the operation
    result = PTDF[m, :]

    for j, bd_index in enumerate(bd_indices):
        for i in range(indptr[j], indptr[j + 1]):
            row_index = indices[i]
            if row_index == m:
                result += data[i] * PTDF[bd_index, :]

    return result


def get_ptdf_comp(mon_br_idx: int, branch_indices: IntVec, mlodf_factors: csc_matrix, PTDF: Mat):
    """
    Get the compensated PTDF values for a single monitored branch
    :param mon_br_idx:
    :param branch_indices:
    :param mlodf_factors:
    :param PTDF:
    :return:
    """
    # PTDFc = MLODF[m, βδ] x PTDF[βδ, :] + PTDF[m, :]
    # PTDFc = mlodf_factors[mon_br_idx, :] @ PTDF[branch_indices, :] + PTDF[mon_br_idx, :]

    res = get_ptdf_comp_numba(data=mlodf_factors.data,
                              indices=mlodf_factors.indices,
                              indptr=mlodf_factors.indptr,
                              PTDF=PTDF,
                              m=mon_br_idx,
                              bd_indices=branch_indices)

    # ok = np.allclose(res, PTDFc[0, :], atol=1e-6)

    return res


class ContingencyTableEntry:
    """
    Entry of a contingency report
    """

    __hdr__ = ["Time",
               "Area 1",
               "Area 2",
               "Monitored",
               "Contingency",
               "Base rating (MW)",
               "Contingency rating (MW)",
               "SRAP rating (MW)",
               "Base flow (MW)",
               "Post-Contingency flow (MW)",
               "Post-SRAP flow (MW)",
               "Base loading (pu)",
               "Post-Contingency loading (pu)",
               "Post-SRAP loading (pu)",
               "Overload",
               "SRAP availability",
               "SRAP Power (MW)",
               "Solved with SRAP"]

    def __init__(self,
                 time_index: int,
                 area_from: str,
                 area_to: str,
                 base_name: str,
                 contingency_name: str,
                 base_rating: float,
                 contingency_rating: float,
                 srap_rating: float,
                 base_flow: complex,
                 post_contingency_flow: complex,
                 post_srap_flow: complex,
                 base_loading: float,
                 post_contingency_loading: float,
                 post_srap_loading: float,
                 msg_ov: str,
                 msg_srap: str,
                 srap_power: float,
                 solved_by_srap: bool = False):
        """
        ContingencyTableEntry constructor
        :param time_index:
        :param area_from:
        :param area_to:
        :param base_name:
        :param contingency_name:
        :param base_rating:
        :param contingency_rating:
        :param srap_rating:
        :param base_flow:
        :param post_contingency_flow:
        :param post_srap_flow:
        :param base_loading:
        :param post_contingency_loading:
        :param post_srap_loading:
        :param msg_ov:
        :param msg_srap:
        :param srap_power:
        :param solved_by_srap:
        """
        self.time_index: int = time_index
        self.area_from: str = area_from
        self.area_to: str = area_to
        self.base_name: str = base_name
        self.contingency_name: str = contingency_name
        self.base_rating: float = base_rating
        self.contingency_rating: float = contingency_rating
        self.srap_rating: float = srap_rating
        self.base_flow: complex = base_flow
        self.post_contingency_flow: complex = post_contingency_flow
        self.post_srap_flow: complex = post_srap_flow
        self.base_loading: float = base_loading
        self.post_contingency_loading: float = post_contingency_loading
        self.post_srap_loading: float = post_srap_loading
        self.msg_ov: str = msg_ov
        self.msg_srap: str = msg_srap
        self.srap_power: float = srap_power
        self.solved_by_srap: bool = solved_by_srap

    def get_headers(self) -> List[str]:
        """
        Get the headers
        :return: list of header names
        """
        return self.__hdr__

    def to_list(self) -> List[Any]:
        """
        Get a list representation of this entry
        :return: List[Any]
        """
        return [self.time_index,
                self.area_from,
                self.area_to,
                self.base_name,
                self.contingency_name,
                self.base_rating,
                self.contingency_rating,
                self.srap_rating,
                self.base_flow,
                self.post_contingency_flow,
                self.post_srap_flow,
                self.base_loading,
                self.post_contingency_loading,
                self.post_srap_loading,
                self.msg_ov,
                self.msg_srap,
                self.srap_power,
                self.solved_by_srap]

    def to_string_list(self) -> List[str]:
        """
        Get list of string values
        :return: List[str]
        """
        return [str(a) for a in self.to_list()]

    def to_array(self) -> StrVec:
        """
        Get array of string values
        :return: StrVec
        """
        return np.array(self.to_string_list())


class ContingencyResultsReport:
    """
    Contingency results report table
    """

    def __init__(self) -> None:
        """
        Constructor
        """
        self.entries: List[ContingencyTableEntry] = list()

    def add_entry(self, entry: ContingencyTableEntry):
        """
        Add contingencies entry
        :param entry: ContingencyTableEntry
        """
        self.entries.append(entry)

    def add(self,
            time_index: int,
            area_from: str,
            area_to: str,
            base_name: str,
            contingency_name: str,
            base_rating: float,
            contingency_rating: float,
            srap_rating: float,
            base_flow: complex,
            post_contingency_flow: complex,
            post_srap_flow: complex,
            base_loading: float,
            post_contingency_loading: float,
            post_srap_loading: float,
            msg_ov: str,
            msg_srap: str,
            srap_power: float,
            solved_by_srap: bool = False):

        """
        Add report data
        :param time_index:
        :param area_from:
        :param area_to:
        :param base_name:
        :param contingency_name:
        :param base_rating:
        :param contingency_rating:
        :param srap_rating:
        :param base_flow:
        :param post_contingency_flow:
        :param post_srap_flow:
        :param base_loading:
        :param post_contingency_loading:
        :param post_srap_loading:
        :param msg_ov:
        :param msg_srap:
        :param srap_power:
        :param solved_by_srap:
        :return:
        """
        self.add_entry(ContingencyTableEntry(
            time_index=time_index,
            area_from=area_from,
            area_to=area_to,
            base_name=base_name,
            contingency_name=contingency_name,
            base_rating=base_rating,
            contingency_rating=contingency_rating,
            srap_rating=srap_rating,
            base_flow=base_flow,
            post_contingency_flow=post_contingency_flow,
            post_srap_flow=post_srap_flow,
            base_loading=base_loading,
            post_contingency_loading=post_contingency_loading,
            post_srap_loading=post_srap_loading,
            msg_ov=msg_ov,
            msg_srap=msg_srap,
            srap_power=srap_power,
            solved_by_srap=solved_by_srap)
        )

    def merge(self, other: "ContingencyResultsReport"):
        """
        Add another ContingencyResultsReport in-place
        :param other: ContingencyResultsReport instance
        """
        self.entries += other.entries

    def size(self) -> int:
        """
        Get the size
        :return: number of entries
        """
        return len(self.entries)

    def n_cols(self) -> int:
        """
        Number of columns
        :return: int
        """
        return len(self.get_headers())

    @staticmethod
    def get_headers() -> list[str]:
        """
        Get the headers
        :return: List[str]
        """
        return ContingencyTableEntry.__hdr__

    def get_index(self) -> IntVec:
        """
        Get the index
        :return: IntVec
        """
        return np.arange(0, self.size())

    def get_data(self) -> StrMat:
        """
        Get data as list of lists of strings
        :return: List[List[str]]
        """
        data = np.empty((self.size(), self.n_cols()), dtype=object)
        for i, e in enumerate(self.entries):
            data[i, :] = e.to_array()
        return data

    def get_df(self) -> pd.DataFrame:
        """
        Get data as pandas DataFrame
        :return: DataFrame
        """
        return pd.DataFrame(data=self.get_data(),
                            index=self.get_index(),
                            columns=self.get_headers())

    def get_summary_table(self) -> pd.DataFrame:
        """

        :return:
        """
        df = self.get_df()

        #
        # # Loading to consider
        # # OJO ES NECESARIO TENER EN CUENTA EL FLUJO EN BASE DE LAS DE EN BASE
        #
        # # Filter by the overloads not acceptables
        # df = df[df["Overload"] == "Overload not acceptable"]
        #
        # # Group de columns by Area1, Area2, Monitored, COntingency
        # df_grp = df.groupby(["Area 1", "Area 2", "Monitored", "Contingency","Base rating (MW)","Contingency rating (MW)","SRAP rating (MW)"])
        #
        # #Compute the columns
        #
        # ov_max = df_grp["C"].max()
        # ov_max_date = df_grp["D"].idxmax().apply(lambda x: df.loc[x, "Time"])
        # ov_avg = df_grp["C"].mean()
        # ov_desvest = df_grp["C"].std()
        # ov_count = df_grp["C"].count()
        #
        # "Overload max (pu)"
        # "Date Overload max"
        # "Overload average (pu)"
        # "Standard deviation (pu)"
        # # "Hours with overload (h)"
        # "Overload count (h x ov)"




        return df

    def __iadd__(self, other: "ContingencyResultsReport"):
        """
        Incremental adition of reports
        :param other: ContingencyResultsReport
        :return: self
        """
        for entry in other.entries:
            self.add_entry(entry)
        return self

    def analyze(self,
                t: Union[None, int],
                mon_idx: IntVec,
                calc_branches: List[Any],
                numerical_circuit: NumericalCircuit,
                base_flow: Vec,
                base_loading: Vec,
                contingency_flows: Vec,
                contingency_loadings: Vec,
                contingency_idx: int,
                contingency_group: ContingencyGroup,
                using_srap: bool = False,
                srap_ratings: Union[Vec, None] = None,
                srap_max_power: float = 1400.0,
                srap_deadband: float = 0.0,
                contingency_deadband: float = 0.0,
                srap_rever_to_nominal_rating: bool = False,
                multi_contingency: LinearMultiContingency = None,
                PTDF: Mat = None,
                available_power: Vec = None,
                srap_used_power: Mat = None,
                F: Vec = None,
                T: Vec = None,
                bus_area_indices: Vec = None,
                area_names: Vec = None,
                top_n: int = 5,
                detailed_massive_report: bool = True):
        """
        Analize contingency resuts and add them to the report
        :param t: time index
        :param mon_idx: array of monitored branch indices
        :param calc_branches: array of calculation branches
        :param numerical_circuit: NumericalCircuit
        :param base_flow: base flows array
        :param base_loading: base loading array
        :param contingency_flows: flows array after the contingency
        :param contingency_loadings: loading array after the contingency
        :param contingency_idx: contingency group index
        :param contingency_group: ContingencyGroup
        :param using_srap: Inspect contingency using the SRAP conditions
        :param srap_ratings: Array of protection ratings of the branches to use with SRAP
        :param srap_max_power: Max amount of power to lower using SRAP conditions
        :param srap_deadband: (in %)
        :param srap_rever_to_nominal_rating:
        :param multi_contingency: list of buses for SRAP conditions
        :param PTDF: PTDF for SRAP conditions
        :param available_power: Array of power avaiable for SRAP
        :param srap_used_power: (branch, nbus) matrix to stre SRAP usage
        :param top_n: maximum number of nodes affecting the oveload
        :param detailed_massive_report: Generate massive report
        """

        # Reporting base case
        if contingency_idx == 0:  # only doing it once per hour

            for m in mon_idx:

                if abs(base_flow[m]) > numerical_circuit.rates[m]:  # only add if overloaded

                    self.add(time_index=t if t is not None else 0,  # --------->Convertir a fecha
                             area_from=area_names[bus_area_indices[F[m]]],
                             area_to=area_names[bus_area_indices[T[m]]],
                             base_name=numerical_circuit.branch_data.names[m],
                             contingency_name='Base',
                             base_rating=numerical_circuit.branch_data.rates[m],
                             contingency_rating=numerical_circuit.branch_data.contingency_rates[m],
                             srap_rating=srap_ratings[m],
                             base_flow=abs(base_flow[m]),
                             post_contingency_flow=0.0,
                             post_srap_flow=0.0,
                             base_loading=abs(base_flow[m]) / (numerical_circuit.rates[m] + 1e-9),
                             post_contingency_loading=0.0,
                             post_srap_loading=0.0,
                             msg_ov='Overload not acceptable',
                             msg_srap='SRAP not applicable',
                             srap_power=0.0,
                             solved_by_srap=False)

        # Now evalueting the effect of contingencies
        for m in mon_idx:  # for each monitored branch ...

            c_flow = abs(contingency_flows[m])
            b_flow = abs(base_flow[m])

            c_load = abs(contingency_loadings[m])

            rate_nx_pu = numerical_circuit.contingency_rates[m] / (numerical_circuit.rates[m] + 1e-9)
            rate_srap_pu = srap_ratings[m] / (numerical_circuit.rates[m] + 1e-9)

            # Affected by contingency?
            affected_by_cont1 = contingency_flows[m] != base_flow[m]
            affected_by_cont2 = c_flow / (b_flow + 1e-9) - 1 > contingency_deadband

            # Only study if the flow is affected enough by contingency,
            # if it produces an overload, and if the variation affects negatively to the flow
            if affected_by_cont1 and affected_by_cont2 and c_load > 1 and c_flow > b_flow:

                # Conditions to set behaviour
                if 1 < c_load <= rate_nx_pu:
                    ov_status = 1
                    msg_ov = 'Overload acceptable'
                    cond_srap = False
                    msg_srap = 'SRAP not needed'
                    solved_by_srap = False
                    post_srap_flow = c_flow
                    max_srap_power = 0.0

                elif rate_nx_pu < c_load <= rate_srap_pu:
                    ov_status = 2
                    msg_ov = 'Overload not acceptable'  # Overwritten if solved
                    cond_srap = True  # Srap aplicable
                    msg_srap = 'SRAP applicable'
                    solved_by_srap = False
                    post_srap_flow = c_flow  # Overwritten if srap activated
                    max_srap_power = 0.0

                elif rate_srap_pu < c_load <= rate_srap_pu + srap_deadband / 100:
                    ov_status = 3
                    msg_ov = 'Overload not acceptable'
                    cond_srap = True
                    msg_srap = 'SRAP not applicable'
                    solved_by_srap = False
                    post_srap_flow = c_flow  # Overwritten if srap activated
                    max_srap_power = 0.0

                elif c_load > rate_srap_pu + srap_deadband / 100:
                    ov_status = 4
                    msg_ov = 'Overload not acceptable'
                    cond_srap = False
                    msg_srap = 'SRAP not applicable'
                    solved_by_srap = False
                    post_srap_flow = c_flow
                    max_srap_power = 0.0
                else:
                    msg_srap = 'Error'
                    ov_status = 0
                    cond_srap = False
                    post_srap_flow = c_flow
                    msg_ov = 'Error'
                    max_srap_power = -99999.999
                    solved_by_srap = False

                if using_srap and cond_srap:

                    # compute the sensitivities for the monitored line with all buses
                    # PTDFc = MLODF[m, βδ] x PTDF[βδ, :] + PTDF[m, :]
                    # PTDFc = multi_contingency.mlodf_factors[m, :] @ PTDF[multi_contingency.branch_indices, :] + PTDF[m, :]
                    PTDFc = get_ptdf_comp(mon_br_idx=m,
                                          branch_indices=multi_contingency.branch_indices,
                                          mlodf_factors=multi_contingency.mlodf_factors,
                                          PTDF=PTDF)

                    # information about the buses that we can use for SRAP
                    sensitivities, indices = get_sparse_array_numba(PTDFc, threshold=1e-3)
                    buses_for_srap = BusesForSrap(branch_idx=m,
                                                  bus_indices=indices,
                                                  sensitivities=sensitivities)

                    if srap_rever_to_nominal_rating:
                        rate_goal = numerical_circuit.rates[m]
                    else:
                        rate_goal = numerical_circuit.contingency_rates[m]

                    solved_by_srap, max_srap_power = buses_for_srap.is_solvable(
                        c_flow=contingency_flows[m].real,  # the real part because it must have the sign
                        rating=rate_goal,
                        srap_pmax_mw=srap_max_power,
                        available_power=available_power,
                        branch_idx=m,
                        top_n=top_n,
                        srap_used_power=srap_used_power
                    )

                    post_srap_flow = abs(c_flow) - abs(max_srap_power)
                    if post_srap_flow < 0:
                        post_srap_flow = 0.0

                    if solved_by_srap and ov_status == 2:
                        msg_ov = 'Overload acceptable'
                    else:
                        msg_ov = 'Overload not acceptable'

                if detailed_massive_report:
                    self.add(time_index=t if t is not None else 0,  # --------->Convertir a fecha
                             area_from=area_names[bus_area_indices[F[m]]],
                             area_to=area_names[bus_area_indices[T[m]]],
                             base_name=numerical_circuit.branch_data.names[m],
                             contingency_name=contingency_group.name,
                             base_rating=numerical_circuit.branch_data.rates[m],
                             contingency_rating=numerical_circuit.branch_data.contingency_rates[m],
                             srap_rating=srap_ratings[m],
                             base_flow=abs(b_flow),
                             post_contingency_flow=abs(c_flow),
                             post_srap_flow=post_srap_flow,
                             base_loading=abs(base_loading[m]),
                             post_contingency_loading=abs(contingency_loadings[m]),
                             post_srap_loading=post_srap_flow / (numerical_circuit.rates[m] + 1e-9),
                             msg_ov=msg_ov,
                             msg_srap=msg_srap,
                             srap_power=abs(max_srap_power),
                             solved_by_srap=solved_by_srap)
