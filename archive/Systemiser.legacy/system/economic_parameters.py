class EconomicParameters:
    def __init__(
        self,
        capex_base=0,
        capex_per_kW=0,
        capex_per_kWh=0,
        opex_base=0,
        opex_per_kW=0,
        opex_per_kWh=0,
        revenue_per_kWh=0,
        lifetime=0,
    ):
        self.capex_base = capex_base
        self.capex_per_kW = capex_per_kW
        self.capex_per_kWh = capex_per_kWh
        self.opex_base = opex_base
        self.opex_per_kW = opex_per_kW
        self.opex_per_kWh = opex_per_kWh
        self.lifetime = lifetime
        self.revenue_per_kWh = revenue_per_kWh
        # self.general_economic_parameters = general_economic_parameters
        self.capex = None
        self.roi = None
        self.pbp = None
        self.lcoe = None
        self.lcos = None
        self.total_lifecycle_cost = None

    def get_capex(self, max_power, max_energy):
        capex = self.capex_base + self.capex_per_kW * max_power / 1e3 + self.capex_per_kWh * max_energy / 1e3
        return capex

    def get_opex(self, peak_power, energy_throughput, N=8760, years=1):
        opex_total = (
            self.opex_base
            + self.opex_per_kW * peak_power / 1e3
            + self.opex_per_kWh * energy_throughput * (8760 / N) * years
        )
        return opex_total

    def get_revenue(self, energy_generated, N=8760, years=1):
        revenue_total = energy_generated * (8760 / N) * self.revenue_per_kWh
        return revenue_total

    def get_cash_flow(self):
        cash_flow = self.revenue_per_year - self.opex_per_year
        return cash_flow

    def get_lifecycle_cost(self):
        if self.capex is not None and self.opex_lifetime is not None:
            lifecycle_cost = self.capex + self.opex_lifetime
        else:
            lifecycle_cost = None
        return lifecycle_cost

    def get_roi(self):
        roi = (self.revenue_per_year * self.lifetime) / (self.lifecycle_cost)
        return roi

    def get_pbp(self):
        pbp = self.capex / (self.revenue_per_year - self.opex_per_year)
        return pbp

    def get_levelised_cost(self, total_energy, N=8760):
        if total_energy == 0:
            return 0
        else:
            levelised_cost = (self.capex + self.opex_per_year * self.lifetime) / (
                total_energy * (8760 / N) * self.lifetime
            )
            return levelised_cost

    def get_annual_cost(self, component, inflation_rate, energy_price_rate, interest_rate, annuity, years):
        annual_costs = []
        for year in range(years):
            # Calculate inflated costs
            capex_inflated = self.capex * ((1 + inflation_rate) ** year)
            opex_inflated = self.opex_total_per_year * ((1 + inflation_rate) ** year)

            # Calculate the annuity for the CAPEX if required
            if annuity and year % self.lifetime == 0:
                annuity_factor = (
                    interest_rate * (1 + interest_rate) ** self.lifetime / ((1 + interest_rate) ** self.lifetime - 1)
                )
                capex_annuity = capex_inflated * annuity_factor
            else:
                capex_annuity = capex_inflated if year % self.lifetime == 0 else 0

            # The total annual cost is the sum of CAPEX annuity and OPEX
            total_annual_cost = capex_annuity + opex_inflated
            annual_costs.append(total_annual_cost)

        return annual_costs

    # def calculate_annual_capex(self, interest_rate, year, include_annuity=True):
    #     """
    #     Calculate the annualized CAPEX.
    #     :param interest_rate: The interest rate for annuity calculation.
    #     :param years: The lifetime over which the CAPEX is spread.
    #     :param include_annuity: If True, calculates annuity-based CAPEX; otherwise, calculates CAPEX for specific years.
    #     :return: Annualized CAPEX if include_annuity is True; otherwise, CAPEX for year 0 and replacement years.
    #     """
    #     if include_annuity:
    #         if interest_rate > 0 and years > 0:
    #             annual_capex = self.capex * (interest_rate * (1 + interest_rate) ** years) / ((1 + interest_rate) ** years - 1)
    #         else:
    #             annual_capex = self.capex / years
    #     else:
    #         # Capex is incurred in year 0 and then every 'years' years (for replacement)
    #         annual_capex = lambda year: self.capex if year % years == 0 else 0

    #     return annual_capex

    # def calculate_cash_flow(self, years=30, include_annuity=False):
    #     annual_capex = self.capex / years if not include_annuity else self.capex * self.interest_rate * (1 + self.interest_rate) ** years / ((1 + self.interest_rate) ** years - 1)
    #     annual_cash_flow = self.revenue_per_year - annual_capex - self.opex_per_year
    #     return annual_cash_flow

    # def calculate_cash_flow(self, energy_price_rate, interest_rate, inflation, include_annuity=False, year=0):
    #     annual_capex = self.capex / years if not include_annuity else self.capex * self.interest_rate * (1 + self.interest_rate) ** year / ((1 + self.interest_rate) ** years - 1)
    #     adjusted_opex = self.opex_per_year * (1 + self.inflation_rate) ** (year - 1)
    #     adjusted_revenue = self.revenue_per_year * (1 + self.energy_price_rate + inflation) ** (year - 1) if include_annuity else self.revenue_per_year
    #     annual_cash_flow = adjusted_revenue - adjusted_opex
    #     return annual_cash_flow

    #     # Default values for economic calculations
    # DEFAULT_PERIOD_YEARS = 30

    # def calculate_component_economics(self, period_years=30):
    #     # Use the default period or a provided override
    #     period_years = period_years or self.DEFAULT_PERIOD_YEARS

    #     # Proceed with calculations using period_years
    #     total_energy_produced = self.calculate_total_energy_produced(period_years)
    #     self.calculate_capex()
    #     self.calculate_opex_per_year(energy_throughput)
    #     self.calculate_opex_lifetime()
    #     self.calculate_total_lifecycle_cost()
    #     self.calculate_total_revenue(total_energy_produced)
    #     self.calculate_roi()
    #     self.calculate_pbp()
    #     self.calculate_lcoe(total_energy_produced)
    #     self.calculate_lcos(total_energy_stored)

    # def calculate_capex(self, component):
    #     max_power  = component.P_max
    #     max_energy = max(component.E) if hasattr(component, 'E') else 0
    #     self.capex = self.capex_base + self.capex_per_kW * max_power / 1e3 + self.capex_per_kWh * max_energy / 1e3

    #     # if component.type == 'storage':
    #     #     max_energy = max(component.E) if hasattr(component, 'E') else 0
    #     #     self.capex += self.capex_per_kWh * max_energy / 1e3  # Add cost per kWh for storage

    # def calculate_opex_per_year(self, component, energy_throughput, N=8760):
    #     # calculate the opex per year for base, size, and flow dependent costs
    #     self.opex_base_per_year = self.opex_base
    #     self.opex_size_per_year = self.opex_per_kW * component.P_max / 1e3
    #     self.opex_flow_per_year = self.opex_per_kWh * energy_throughput * (8760 / N)
    #     self.opex_total_per_year = self.opex_base_per_year + self.opex_size_per_year + self.opex_flow_per_year
    #     return self.opex_total_per_year

    # def calculate_opex_lifetime(self):
    #     self.opex_base_lifetime = self.opex_base_per_year * self.lifetime
    #     self.opex_size_lifetime = self.opex_size_per_year * self.lifetime
    #     self.opex_flow_lifetime = self.opex_flow_per_year * self.lifetime
    #     self.opex_total_lifetime = self.opex_base_lifetime + self.opex_size_lifetime + self.opex_flow_lifetime
    #     return self.opex_total_lifetime

    # def calculate_lcos(self, total_energy_stored, N=8760, years=20):
    #     if total_energy_stored and total_energy_stored != 0:
    #         lcos = (self.capex + self.opex_year * years) / (total_energy_stored * (8760 / N) * years)
    #     else:
    #         lcos = None
    #     return lcos

    # def calculate_lcos(self, component, total_energy_stored):
    #     if total_energy_stored and total_energy_stored != 0 and component.type == "storage":
    #         self.lcos = self.total_lifecycle_cost / total_energy_stored
    #     else:
    #         self.lcos = None
    #     return self.lcos

    # def calculate_opex_per_year(self, peak_power, energy_throughput, N=8760):
    #     # Calculate the OPEX per year based on peak power and energy throughput
    #     self.opex_base_per_year = self.opex_base
    #     self.opex_size_per_year = self.opex_per_kW * peak_power / 1e3
    #     self.opex_flow_per_year = self.opex_per_kWh * energy_throughput * (8760 / N)
    #     opex_total_per_year = self.opex_base_per_year + self.opex_size_per_year + self.opex_flow_per_year
    #     return opex_total_per_year

    # def calculate_opex_lifetime(self):
    #     # Calculate the OPEX over the lifetime
    #     self.opex_base_lifetime = self.opex_base_per_year * self.lifetime
    #     self.opex_size_lifetime = self.opex_size_per_year * self.lifetime
    #     self.opex_flow_lifetime = self.opex_flow_per_year * self.lifetime
    #     opex_total_lifetime = self.opex_base_lifetime + self.opex_size_lifetime + self.opex_flow_lifetime
    #     return opex_total_lifetime

    # def calculate_component_annual_cost(self, annuity=True, years=30):
    #     # Use pre-calculated CAPEX and OPEX
    #     capex = self.capex
    #     opex_per_year = self.opex_total_per_year

    #     # Calculate annual CAPEX if annuity is considered
    #     if annuity:
    #         annual_capex = capex * self.interest_rate * (1 + self.interest_rate) ** years / ((1 + self.interest_rate) ** years - 1)
    #     else:
    #         annual_capex = capex / years

    #     # Calculate total annual cost
    #     total_annual_cost = annual_capex + opex_per_year
    #     return total_annual_cost

    # def calculate_total_revenue(self, total_energy_generated):
    #     if total_energy_generated and total_energy_generated != 0:
    #         self.total_revenue = self.revenue_per_kWh * total_energy_generated
    #     else:
    #         self.total_revenue = None
    #     return self.total_revenue

    # def calculate_roi_OLD(self):
    #     if self.total_revenue and self.total_lifecycle_cost and self.total_lifecycle_cost != 0:
    #         self.roi = (self.total_revenue - self.total_lifecycle_cost) / self.total_lifecycle_cost
    #     else:
    #         self.roi = None
    #     return self.roi

    # def calculate_pbp_OLD(self):
    #     if self.total_revenue and self.total_lifecycle_cost and self.total_revenue != 0:
    #         self.pbp = self.total_lifecycle_cost / self.total_revenue
    #     else:
    #         self.pbp = None
    #     return self.pbp

    # def calculate_lcoe(self, component, total_energy_generated):
    #     if total_energy_generated and total_energy_generated != 0 and component.type == "generation":
    #         self.lcoe = self.total_lifecycle_cost / total_energy_generated
    #     else:
    #         self.lcoe = None
    #     return self.lcoe

    # def calculate_lcos(self, component, total_energy_stored):
    #     if total_energy_stored and total_energy_stored != 0 and component.type == "storage":
    #         self.lcos = self.total_lifecycle_cost / total_energy_stored
    #     else:
    #         self.lcos = None
    #     return self.lcos
