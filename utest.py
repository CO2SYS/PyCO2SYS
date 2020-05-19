import PyCO2SYS as pyco2
import numpy as np

par1 = np.array([2150, 2150, 2020])
par2 = np.array([2300, 2200, 2100])
par1type = np.array([2, 2, 2])
par2type = 1
sal = 32
tempin = 10
tempout = 20
presin = 0
presout = 1000
si = 10
phos = 3
nh3 = 1
h2s = 0.5
phscale = 1
k1k2c = 10
kso4c = 3
kfc = 1

co2dict = pyco2.CO2SYS(
    par1,
    par2,
    par1type,
    par2type,
    sal,
    tempin,
    tempout,
    presin,
    presout,
    si,
    phos,
    phscale,
    k1k2c,
    kso4c,
    KFCONSTANT=kfc,
)

co2j, co2j_cols = pyco2.uncertainty.jacobians(
    co2dict, ["CO2out", "OmegaARin"], ["PAR1", "TEMPIN"])
print(co2j)

co2u = pyco2.uncertainty.automatic.pars2core(co2dict, uncertainties=["PAR1", "PAR2"])
