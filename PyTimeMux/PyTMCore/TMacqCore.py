#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar  5 14:13:45 2019

@author: aguimera
"""
import PyqtTools.DaqInterface as DaqInt
import numpy as np
# import HwConf.MainBoard_16x16 as MyConf


class ChannelsConfig():

    # DCChannelIndex[ch] = (index, sortindex)
    DCChannelIndex = None
    ACChannelIndex = None
    ChNamesList = None
    AnalogInputs = None
    DigitalOutputs = None

    # Events list
    DataEveryNEvent = None
    DataDoneEvent = None

    ClearSig = np.zeros((1, len(MyConf.Inputs[1])),
                        dtype=np.bool).astype(np.uint8)
    ClearSig = np.hstack((ClearSig, ClearSig))

    def _InitAnalogInputs(self):
        print('InitAnalogInputs')
        self.DCChannelIndex = {}
        self.ACChannelIndex = {}
        InChans = []
        index = 0
        sortindex = 0
        for ch in self.ChNamesList:
            if self.AcqDC:
                InChans.append(self.aiChannels[ch][0])
                self.DCChannelIndex[ch] = (index, sortindex)
                index += 1
                print(ch, ' DC -->', self.aiChannels[ch][0])
                print('SortIndex ->', self.DCChannelIndex[ch])
            if self.AcqAC:
                InChans.append(self.aiChannels[ch][1])
                self.ACChannelIndex[ch] = (index, sortindex)
                index += 1
                print(ch, ' AC -->', self.aiChannels[ch][1])
                print('SortIndex ->', self.ACChannelIndex[ch])
            sortindex += 1
        print('Input ai', InChans)

        self.AnalogInputs = DaqInt.ReadAnalog(InChans=InChans)
        # events linking
        self.AnalogInputs.EveryNEvent = self.EveryNEventCallBack
        self.AnalogInputs.DoneEvent = self.DoneEventCallBack

    def _InitDigitalOutputs(self):
        print('InitDigitalOutputs')
        print(self.DigColumns)
        DOChannels = []

        for digc in sorted(self.DigColumns):
        # for digc in sorted(self.doColumns):
            print(digc)
            DOChannels.append(self.doColumns[digc][0])
#            DOChannels.append(doColumns[digc][0])
            DOChannels.append(self.doColumns[digc][1])
        print(DOChannels)

#        DOChannels = []
#
#        for digc in self.DigColumns:
#            DOChannels.append(doColumns[digc][0])
#            DOChannels.append(doColumns[digc][1])

        self.DigitalOutputs = DaqInt.WriteDigital(Channels=DOChannels)

    def _InitAnalogOutputs(self, ChVds, ChVs):
        print('ChVds ->', ChVds)
        print('ChVs ->', ChVs)
        self.VsOut = DaqInt.WriteAnalog((ChVs,))
        self.VdsOut = DaqInt.WriteAnalog((ChVds,))

    def __init__(self, Channels, DigColumns,
                 AcqDC=True, AcqAC=True,
                 ChVds='ao0', ChVs='ao1',
                 ACGain=1.1e5, DCGain=10e3, Board='MainBoard'):
        print('InitChannels')
        self._InitAnalogOutputs(ChVds=ChVds, ChVs=ChVs)

        self.ChNamesList = sorted(Channels)
        print(self.ChNamesList)
        self.AcqAC = AcqAC
        self.AcqDC = AcqDC
        self.ACGain = ACGain
        self.DCGain = DCGain
        print('Board---->', Board)

        if Board == 'MainBoard':
            self.aiChannels = MyConf.Inputs[0]
            self.doColumns = MyConf.Inputs[1]
        else:
            self.aiChannels = MyConf.Inputs[0]
            self.doColumns = MyConf.Inputs[1]

        self._InitAnalogInputs()

        self.DigColumns = sorted(DigColumns)
        self._InitDigitalOutputs()

        MuxChannelNames = []
        for Row in self.ChNamesList:
            for Col in self.DigColumns:
                MuxChannelNames.append(Row + Col)
        self.MuxChannelNames = MuxChannelNames
        print(self.MuxChannelNames)

        if self.AcqAC and self.AcqDC:
            self.nChannels = len(self.MuxChannelNames)*2
        else:
            self.nChannels = len(self.MuxChannelNames)

    def StartAcquisition(self, Fs, nSampsCo, nBlocks, Vgs, Vds, **kwargs):
        print('StartAcquisition')
        self.SetBias(Vgs=Vgs, Vds=Vds)
        self.SetDigitalOutputs(nSampsCo=nSampsCo)
        print('DSig set')
        self.nBlocks = nBlocks
        self.nSampsCo = nSampsCo
#        self.OutputShape = (nColumns * nRows, nSampsCh, nblocs)
        self.OutputShape = (len(self.MuxChannelNames), nSampsCo, nBlocks)
        EveryN = len(self.DigColumns)*nSampsCo*nBlocks
        self.AnalogInputs.ReadContData(Fs=Fs,
                                       EverySamps=EveryN)

    def SetBias(self, Vgs, Vds):
        print('ChannelsConfig SetBias Vgs ->', Vgs, 'Vds ->', Vds)
        self.VdsOut.SetVal(Vds)
        self.VsOut.SetVal(-Vgs)
        self.BiasVd = Vds-Vgs
        self.Vgs = Vgs
        self.Vds = Vds

    def SetDigitalOutputs(self, nSampsCo):
        print('SetDigitalOutputs')
        DOut = np.array([], dtype=np.bool)

        for nCol, iCol in zip(range(len(self.doColumns)), sorted(list(self.doColumns.keys()))):
            Lout = np.zeros((1, nSampsCo*len(self.DigColumns)), dtype=np.bool)
            for i, n in enumerate(self.DigColumns):
                if n == iCol:
                    Lout[0, nSampsCo * i: nSampsCo * (i + 1)] = True
                Cout = np.vstack((Lout, ~Lout))
            DOut = np.vstack((DOut, Cout)) if DOut.size else Cout

        SortDInds = []
        for line in DOut[0:-1:2, :]:
            if True in line:
                SortDInds.append(np.where(line))

        self.SortDInds = SortDInds
        self.DigitalOutputs.SetContSignal(Signal=DOut.astype(np.uint8))

    def _SortChannels(self, data, SortDict):
        # Sort by aianalog input
        (samps, inch) = data.shape
        aiData = np.zeros((samps, len(SortDict)))
        for chn, inds in sorted(SortDict.items()):
            aiData[:, inds[1]] = data[:, inds[0]]

        # Sort by digital columns
        aiData = aiData.transpose()
        MuxData = np.ndarray(self.OutputShape)

        nColumns = len(self.DigColumns)
        for indB in range(self.nBlocks):
            startind = indB * self.nSampsCo * nColumns
            stopind = self.nSampsCo * nColumns * (indB + 1)
            Vblock = aiData[:, startind: stopind]
            ind = 0
            for chData in Vblock[:, :]:
                for Inds in self.SortDInds:
                    MuxData[ind, :, indB] = chData[Inds]
                    ind += 1
        return aiData, MuxData

    def EveryNEventCallBack(self, Data):
        _DataEveryNEvent = self.DataEveryNEvent

        if _DataEveryNEvent is not None:
            if self.AcqDC:
                aiDataDC, MuxDataDC = self._SortChannels(Data,
                                                         self.DCChannelIndex)
                aiDataDC = (aiDataDC-self.BiasVd) / self.DCGain
                MuxDataDC = (MuxDataDC-self.BiasVd) / self.DCGain
            if self.AcqAC:
                aiDataAC, MuxDataAC = self._SortChannels(Data,
                                                         self.ACChannelIndex)
                aiDataAC = aiDataAC / self.ACGain
                MuxDataAC = MuxDataAC / self.ACGain

            if self.AcqAC and self.AcqDC:
                aiData = np.vstack((aiDataDC, aiDataAC))
                MuxData = np.vstack((MuxDataDC, MuxDataAC))
                _DataEveryNEvent(aiData, MuxData)
            elif self.AcqAC:
                _DataEveryNEvent(aiDataAC, MuxDataAC)
            elif self.AcqDC:
                _DataEveryNEvent(aiDataDC, MuxDataDC)

    def DoneEventCallBack(self, Data):
        print('Done callback')

    def Stop(self):
        print('Stopppp')
        self.SetBias(Vgs=0, Vds=0)
        self.AnalogInputs.StopContData()
        if self.DigitalOutputs is not None:
            print('Clear Digital')
#            self.DigitalOutputs.SetContSignal(Signal=self.ClearSig)
            self.DigitalOutputs.ClearTask()
            self.DigitalOutputs = None


#    def __del__(self):
#        print('Delete class')
#        self.Inputs.ClearTask()
#
