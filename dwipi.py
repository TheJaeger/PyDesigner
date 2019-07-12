import numpy as np
from scipy.special import expit as sigmoid
import nibabel as nib
import os
import multiprocessing
from joblib import Parallel, delayed
from tqdm import tqdm
import random as rnd

# Define the lowest number possible before it is considred a zero
minZero = 1e-8

# Define number of directions to resample after computing all tensors
dirSample = 256

class DWI(object):
    def __init__(self, imPath):
        if os.path.exists(imPath):
            assert isinstance(imPath, object)
            self.hdr = nib.load(imPath)
            self.img = np.array(self.hdr.dataobj)
            (path, file) = os.path.split(imPath)               # Get just NIFTI filename + extension
            fName = os.path.splitext(file)[0]                   # Remove extension from NIFTI filename
            bvalPath = os.path.join(path, fName + '.bval')      # Add .bval to NIFTI filename
            bvecPath = os.path.join(path, fName + '.bvec')      # Add .bvec to NIFTI filename
            if os.path.exists(bvalPath) and os.path.exists(bvecPath):
                bvecs = np.loadtxt(bvecPath)                    # Load bvecs
                bvals = np.rint(np.loadtxt(bvalPath))           # Load bvals
                self.grad = np.c_[np.transpose(bvecs), bvals]   # Combine bvecs and bvals into [n x 4] array where n is
                                                                #   number of DWI volumes. [Gx Gy Gz Bval]
            else:
                assert('Unable to locate BVAL or BVEC files')
            maskPath = os.path.join(path,'brain_mask.nii')
            if os.path.exists(maskPath):
                tmp = nib.load(maskPath)
                self.mask = np.array(tmp.dataobj)
                self.maskStatus = True
                print('Found brain mask')
            else:
                self.mask = np.ones((self.img.shape[0], self.img.shape[1], self.img.shape[2]), order='F')
                self.maskStatus = False
                print('No brain mask found')
        else:
            assert('File in path not found. Please locate file and try again')
        print('Image ' + fName + '.nii loaded successfully')

    def getBvals(self):
        """
        Returns a vector of b-values, requires no input arguments
        Classification: Method

        Usage
        -----
        bvals = dwi.getBvals(), where dwi is the DWI class object
        """
        return self.grad[:,3]

    def getBvecs(self):
        """
        Returns an array of gradient vectors, requires no input parameters
        Classification: Method

        Usage
        -----
        bvecs = dwi.getBvecs(), where dwi is the DWI class object
        """
        return self.grad[:,0:3]

    def maxBval(self):
        """
        Returns the maximum b-value in a dataset to determine between DTI and DKI, requires no input parameters
        Classification: Method

        Usage
        -----
        a = dwi.maxBval(), where dwi is the DWI class object

        """
        return max(np.unique(self.grad[:,3]))

    def tensorType(self):
        """
        Returns whether input image is DTI or DKI compatible, requires no input parameters
        Classification: Method

        Usage
        -----
        a = dwi.tensorType(), where dwi is the DWI class object

        Returns
        -------
        a: 'dti' or 'dki' (string)
        """
        if self.maxBval() <= 1500:
            type = 'dti'
        elif self.maxBval() > 1500:
            type = 'dki'
        else:
            raise ValueError('tensortype: Error in determining maximum BVAL')
        return type

    def createTensorOrder(self, order=None):
        """
        Creates tensor order array and indices
        Classification: Method

        Usage
        -----
        (cnt ind) = dwi.createTensorOrder(order)

        Parameters
        ----------
        order: 2 or 4 (int or None)
               Tensor order number, 2 for diffusion and 4 for kurtosis. Default: None; auto-detect

        Returns
        -------
        cnt: vector (int)
        ind: array (int)

        Additional Information
        ----------------------
        The tensors for this pipeline are based on NYU's designer layout as depicted in the table below. This will soon
        be depreciated and updated with MRTRIX3's layout.
        =============================
        ------D------
        1  |    D11
        2  |    D12
        3  |    D13
        4  |    D22
        5  |    D23
        6  |    D33
        ------K------
       1  |   W1111
       2  |   W1112
       3  |   W1113
       4  |   W1122
       5  |   W1123
       6  |   W1133
       7  |   W1222
       8  |   W1223
       9  |   W1233
       10 |   W1333
       11 |   W2222
       12 |   W2223
       13 |   W2233
       14 |   W2333
       15 |   W3000
        """
        imType = self.tensorType()
        if order is None:
            if imType == 'dti':
                cnt = np.array([1, 2, 2, 1, 2, 1], dtype=int)
                ind = np.array(([1, 1], [1, 2], [1, 3], [2, 2], [2, 3], [3, 3])) - 1
            elif imType == 'dki':
                cnt = np.array([1, 4, 4, 6, 12, 6, 4, 12, 12, 4, 1, 4, 6, 4, 1], dtype=int)
                ind = np.array(([1, 1, 1, 1], [1, 1, 1, 2], [1, 1, 1, 3], [1, 1, 2, 2], [1, 1, 2, 3], [1, 1, 3, 3], \
                                [1, 2, 2, 2], [1, 2, 2, 3], [1, 2, 3, 3], [1, 3, 3, 3], [2, 2, 2, 2], [2, 2, 2, 3],
                                [2, 2, 3, 3], [2, 3, 3, 3], [3, 3, 3, 3])) - 1
        elif order == 2:
            cnt = np.array([1, 2, 2, 1, 2, 1], dtype=int)
            ind = np.array(([1, 1], [1, 2], [1, 3], [2, 2], [2, 3], [3, 3])) - 1
        elif order == 4:
            cnt = np.array([1, 4, 4, 6, 12, 6, 4, 12, 12, 4, 1, 4, 6, 4, 1], dtype=int)
            ind = np.array(([1,1,1,1],[1,1,1,2],[1,1,1,3],[1,1,2,2],[1,1,2,3],[1,1,3,3],\
                [1,2,2,2],[1,2,2,3],[1,2,3,3],[1,3,3,3],[2,2,2,2],[2,2,2,3],[2,2,3,3],[2,3,3,3],[3,3,3,3])) - 1
        else:
            raise ValueError('createTensorOrder: Please enter valid order values (2 or 4).')
        return cnt, ind

    def vectorize(self, dwi, mask):
        """
        Returns vectorized image based on brain mask, requires no input parameters
        If the input is 1D or 2D, unpatch it to 3D or 4D using a mask
        If the input is 3D or 4D, vectorize it using a mask
        Classification: Method

        Usage
        -----
        vec = dwi.vectorize(img) if there's no mask
        vec = dwi.vectorize(img, mask) if there's a mask

        Returns
        -------
        vec: N X number_of_voxels vector or array, where N is the number of DWI volumes
        """
        if mask is None:
            mask = np.ones((dwi.shape[0], dwi.shape[1], dwi.shape[2]), order='F')
        mask = mask.astype(bool)
        if dwi.ndim == 1:
            dwi = np.expand_dims(dwi, axis=0)
        if dwi.ndim == 2:
            n = dwi.shape[0]
            s = np.zeros((mask.shape[0], mask.shape[1], mask.shape[2], n), order='F')
            for i in range(0, n):
                s[:,:,:,i] = np.reshape(dwi[i,:], (mask.shape), order='F')
        if dwi.ndim == 3:
            dwi = np.expand_dims(dwi, axis=-1)
        if dwi.ndim == 4:
            s = np.zeros((dwi.shape[-1], np.sum(mask).astype(int)), order='F')
            for i in range(0, dwi.shape[-1]):
                tmp = dwi[:,:,:,i]
                maskind = np.ma.array(tmp, mask=mask)
                s[i,:] = np.ma.ravel(maskind, order='F').data

        return np.squeeze(s)

    def fibonacciSphere(self, samples=1, randomize=True):
        """
        Returns "samples" evenly spaced points on a sphere
        :param samples:
        :param randomize:
        :return:
        """
        import random
        rnd = 1
        if randomize:
            rnd = random.random() * samples
        points = []
        offset = 2/samples
        increment = np.pi * (3. - np.sqrt(5.))
        for i in range(samples):
            y = ((i * offset) - 1) + (offset / 2)
            r = np.sqrt(1 - pow(y,2))
            phi = ((i + rnd) % samples) * increment
            x = np.cos(phi) * r
            z = np.sin(phi) * r
            points.append([x,y,z])
        return points

    def radialSampling(self, dir, n):
        # get the radial component of a set of directions
        dt = 2*np.pi/n
        theta = np.arange(0,2*np.pi-dt,dt)
        dirs = np.vstack((np.cos(theta), np.sin(theta), 0*theta))
        v = np.hstack((-dir[1], dir[0], 0))
        s = np.sqrt(np.sum(v**2))
        c = dir[2]
        V = np.array([[0, -v[2], v[1]],[v[2], 0, -v[0]],[-v[1], v[0], 0]])
        R = np.eye(3) + V + np.matmul(V,V) * (1-c)/(s**2)
        dirs = np.matmul(R, dirs)
        return dirs

    def diffusionCoeff(self, dt, dir):
        # compute ADC
        dcnt, dind = self.createTensorOrder(2)
        ndir = dir.shape[0]
        bD = np.tile(dcnt,(ndir, 1)) * dir[:,dind[:, 0]] * dir[:,dind[:, 1]]
        adc = np.matmul(bD, dt)
        return adc

    def kurtosisCoeff(self, dt, dir):
        # compute AKC
        wcnt, wind = self.createTensorOrder(4)
        ndir = dir.shape[0]
        adc = self.diffusionCoeff(dt[:6], dir)
        md = np.sum(dt[np.array([0,3,5])], 0)/3
        bW = np.tile(wcnt,(ndir, 1)) * dir[:,wind[:, 0]] * dir[:,wind[:, 1]] * dir[:,wind[:, 2]] * dir[:,wind[:, 3]]
        akc = np.matmul(bW, dt[6:])
        akc = (akc * np.tile(md**2, (adc.shape[0], 1)))/(adc**2)
        return akc

    def dtiTensorParams(self, nn):
        # compute dti tensor eigenvalues and eigenvectors and sort them
        values, vectors = np.linalg.eig(nn)
        idx = np.argsort(-values)
        values = -np.sort(-values)
        vectors = vectors[:, idx]
        return values, vectors

    def dkiTensorParams(self, v1, dt):
        # kurtosis tensor parameters use average directional
        # statistics to approximate ak and rk
        dirs = np.vstack((v1, -v1))
        akc = self.kurtosisCoeff(dt, dirs)
        ak = np.mean(akc)
        dirs = self.radialSampling(v1, dirSample).T
        akc = self.kurtosisCoeff(dt, dirs)
        rk = np.mean(akc)
        return ak, rk

    def wlls(self, shat, dwi, b):
        # compute a wlls fit using weights from inital fit shat
        w = np.diag(shat)
        dt = np.matmul(np.linalg.pinv(np.matmul(w, b)), np.matmul(w, np.log(dwi)))
        # for constrained fitting I'll need to modify this line. It is much slower than pinv so lets ignore for now.
        #dt = opt.lsq_linear(np.matmul(w, b), np.matmul(w, np.log(dwi)), \
        #     method='bvls', tol=1e-12, max_iter=22000, lsq_solver='exact')
        return dt

    def fit(self):
        """
        Returns fitted diffusion or kurtosis tensor
        :return:
        """
        order = np.floor(np.log(np.abs(np.max(self.grad[:,-1])+1))/np.log(10))
        if order >= 2:
            self.grad[:, -1] = self.grad[:, -1]/1000

        self.img.astype(np.double)
        self.img[self.img <= 0] = np.finfo(np.double).eps

        self.grad.astype(np.double)
        normgrad = np.sqrt(np.sum(self.grad[:,:3]**2, 1))
        normgrad[normgrad == 0] = 1

        self.grad[:,:3] = self.grad[:,:3]/np.tile(normgrad, (3,1)).T
        self.grad[np.isnan(self.grad)] = 0

        dcnt, dind = self.createTensorOrder(2)
        wcnt, wind = self.createTensorOrder(4)

        ndwis = self.img.shape[-1]
        bs = np.ones((ndwis, 1))
        bD = np.tile(dcnt,(ndwis, 1))*self.grad[:,dind[:, 0]]*self.grad[:,dind[:, 1]]
        bW = np.tile(wcnt,(ndwis, 1))*self.grad[:,wind[:, 0]]*self.grad[:,wind[:, 1]]*self.grad[:,wind[:, 2]]*self.grad[:,wind[:, 3]]
        self.b = np.concatenate((bs, (np.tile(-self.grad[:,-1], (6,1)).T*bD), np.squeeze(1/6*np.tile(self.grad[:,-1], (15,1)).T**2)*bW), 1)

        dwi_ = self.vectorize(self.img, None)
        init = np.matmul(np.linalg.pinv(self.b), np.log(dwi_))
        shat = np.exp(np.matmul(self.b, init))

        print('...fitting with wlls')
        inputs = tqdm(range(0, dwi_.shape[1]))
        num_cores = multiprocessing.cpu_count()
        self.dt = Parallel(n_jobs=num_cores,prefer='processes')\
            (delayed(self.wlls)(shat[:,i], dwi_[:,i], self.b) for i in inputs)
        self.dt = np.reshape(self.dt, (dwi_.shape[1], self.b.shape[1])).T
        self.s0 = np.exp(self.dt[0,:])
        self.dt = self.dt[1:,:]
        D_apprSq = 1/(np.sum(self.dt[(0,3,5),:], axis=0)/3)**2
        self.dt[6:,:] = self.dt[6:,:]*np.tile(D_apprSq, (15,1))
        return self.dt

    def extract(self):
        # extract all tensor parameters from dt
        num_cores = multiprocessing.cpu_count()

        print('...extracting dti parameters')
        DT = np.reshape(
            np.concatenate((self.dt[0, :], self.dt[1, :], self.dt[2, :], self.dt[1, :], self.dt[3, :], self.dt[4, :], self.dt[2, :], self.dt[4, :], self.dt[5, :])),
            (3, 3, self.dt.shape[1]))

        # get the trace
        rdwi = sigmoid(np.matmul(self.b[:, 1:], self.dt))
        B = np.round(-(self.b[:, 0] + self.b[:, 3] + self.b[:, 5]) * 1000)
        uB = np.unique(B)
        trace = np.zeros((self.dt.shape[1], uB.shape[0]))
        for ib in range(0, uB.shape[0]):
            t = np.where(B == uB[ib])
            trace[:, ib] = np.mean(rdwi[t[0], :], axis=0)

        nvox = self.dt.shape[1]
        inputs = tqdm(range(0, nvox))
        values, vectors = zip(*Parallel(n_jobs=num_cores, prefer='processes') \
            (delayed(self.dtiTensorParams)(DT[:, :, i]) for i in inputs))
        values = np.reshape(np.abs(values), (nvox, 3))
        vectors = np.reshape(vectors, (nvox, 3, 3))

        print('...extracting dki parameters')
        self.dirs = np.array(self.fibonacciSphere(dirSample, True))
        akc = self.kurtosisCoeff(self.dt, self.dirs)
        mk = np.mean(akc, 0)
        ak, rk = zip(*Parallel(n_jobs=num_cores, prefer='processes') \
            (delayed(self.dkiTensorParams)(vectors[i, :, 0], self.dt[:, i]) for i in inputs))
        ak = np.reshape(ak, (nvox))
        rk = np.reshape(rk, (nvox))

        l1 = self.vectorize(values[:, 0], self.mask)
        l2 = self.vectorize(values[:, 1], self.mask)
        l3 = self.vectorize(values[:, 2], self.mask)
        v1 = self.vectorize(vectors[:, :, 0].T, self.mask)

        md = (l1 + l2 + l3) / 3
        rd = (l2 + l3) / 2
        ad = l1
        fa = np.sqrt(1 / 2) * np.sqrt((l1 - l2) ** 2 + (l2 - l3) ** 2 + (l3 - l1) ** 2) / np.sqrt(
            l1 ** 2 + l2 ** 2 + l3 ** 2)
        trace = self.vectorize(trace.T, self.mask)
        fe = np.abs(np.stack((fa * v1[:, :, :, 0], fa * v1[:, :, :, 1], fa * v1[:, :, :, 2]), axis=3))
        ak = self.vectorize(ak, self.mask)
        rk = self.vectorize(rk, self.mask)
        mk = self.vectorize(mk, self.mask)
        return md, rd, ad, fa, fe, trace, mk, ak, rk

    def findViols(self, c=[0, 1, 0]):
        """
        Returns a 3D violation map of voxels that violate constraints.
        Classification: Method

        Usage
        -----
        map = findViols(img, [0 1 0]

        Parameters
        ----------
        img: 3D metric array such as mk or fa
        c:   [3 x 1] vector that toggles which constraints to check
             c[0]: Check D < 0 constraint
             c[1]: Check K < 0 constraint (default)
             c[2]: Check K > 3/(b*D) constraint

        Returns
        -------
        map: 3D array containing locations of voxels that incur directional violations. Voxels with values contain
             violaions and voxel values represent proportion of directional violations.

        """
        if c == None:
            c = [0, 0, 0]

        nvox = self.dt.shape[1]
        sumViols = np.zeros(nvox)
        maxB = self.maxBval()
        adc = self.diffusionCoeff(self.dt[:6], self.dirs)
        akc = self.kurtosisCoeff(self.dt, self.dirs)
        tmp = np.zeros(3)
        print('...computing directional violations')
        for i in range(nvox):
            # C[0]: D < 0
            tmp[0] = np.size(np.nonzero(adc[:, i] < minZero))
            # C[1]: K < 0
            tmp[1] = np.size(np.nonzero(akc[:, i] < minZero))
            #c[2]:
            tmp[2] = np.size(np.nonzero(akc[:, i] > (3/(maxB * adc[:, i]))))
            sumViols[i] = np.sum(tmp)

        map = np.zeros((sumViols.shape))
        if c[0] == 0 and c[1] == 0 and c[2] == 0:
            # [0 0 0]
            print('0 0 0')
            map = pViols

        elif c[0] == 1 and c[1] == 0 and c[2] == 0:
            # [1 0 0]
            print('1 0 0')
            map = sumViols/dirSample

        elif c[0] == 0 and c[1] == 1 and c[2] == 0:
            # [0 1 0]
            print('0 1 0')
            map = sumViols/dirSample

        elif c[0] == 0 and c[1] == 0 and c[2] == 1:
            # [0 0 1]
            print('0 0 1')
            map = sumViols/dirSample

        elif c[0] == 1 and c[1] == 1 and c[2] == 0:
            # [1 1 0]
            print('1 1 0')
            map = sumVioms/(2 * dirSample)

        elif c[0] == 1 and c[1] == 0 and c[2] == 1:
            # [1 0 1]
            print('1 0 1')
            map = sumViols/(2 * dirSample)

        elif c[0] == 0 and c[1] == 1 and c[2] == 1:
            # [0 1 1]
            print('0 1 1')
            map = sumViols / (2 * dirSample)

        elif c[0] == 1 and c[1] == 1 and c[2] == 1:
            # [1 1 1]
            print('1 1 1')
            map = sumViols / (3 * dirSample)

        map = np.reshape(map, nvox)
        map = self.vectorize(map, self.mask)
        return map

    def findVoxelViol(self, adcVox, akcVox, maxB, c):
        """
        Returns the proportiona of vioaltions occuring at a voxel.
        Classification: Method

        Usage
        -----
        map = findViols(voxel, [0 1 0]

        Parameters
        ----------
        img: 3D metric array such as mk or fa
        c:   [3 x 1] vector that toggles which constraints to check
             c[0]: Check D < 0 constraint
             c[1]: Check K < 0 constraint (default)
             c[2]: Check K > 3/(b*D) constraint

        Returns
        -------
        n: Number ranging from 0 to 1 that indicates proportion of violations occuring at voxel.

        """
        tmp = np.zeros(3)
        # C[0]: D < 0
        tmp[0] = np.size(np.nonzero(adcVox < minZero))
        # C[1]: K < 0
        tmp[1] = np.size(np.nonzero(akcVox < minZero))
        #c[2]:K > 3/(b * D)
        tmp[2] = np.size(np.nonzero(akcVox > (3/(maxB * adcVox))))
        sumViols = np.sum(tmp)

        if c[0] == 0 and c[1] == 0 and c[2] == 0:
            # [0 0 0]
            n = 0

        elif c[0] == 1 and c[1] == 0 and c[2] == 0:
            # [1 0 0]
            n = sumViols/dirSample

        elif c[0] == 0 and c[1] == 1 and c[2] == 0:
            # [0 1 0]
            n = sumViols/dirSample

        elif c[0] == 0 and c[1] == 0 and c[2] == 1:
            # [0 0 1]
            n = sumViols/dirSample

        elif c[0] == 1 and c[1] == 1 and c[2] == 0:
            # [1 1 0]
            n = sumVioms/(2 * dirSample)

        elif c[0] == 1 and c[1] == 0 and c[2] == 1:
            # [1 0 1]
            n = sumViols/(2 * dirSample)

        elif c[0] == 0 and c[1] == 1 and c[2] == 1:
            # [0 1 1]
            n = sumViols/(2 * dirSample)

        elif c[0] == 1 and c[1] == 1 and c[2] == 1:
            # [1 1 1]
            n = sumViols/(3 * dirSample)
        return n

    def parfindViols(self, c=[0, 0, 0]):
        if c == None:
            c = [0, 0, 0]
        print('...computing directional violations (parallel)')
        nvox = self.dt.shape[1]
        map = np.zeros(nvox)
        maxB = self.maxBval()
        adc = self.diffusionCoeff(self.dt[:6], self.dirs)
        akc = self.kurtosisCoeff(self.dt, self.dirs)
        num_cores = multiprocessing.cpu_count()
        inputs = tqdm(range(0, nvox))
        map = Parallel(n_jobs=num_cores, prefer='processes') \
            (delayed(self.findVoxelViol)(adc[:,i], akc[:,i], maxB, [0, 1, 0]) for i in inputs)
        map = np.reshape(pViols2, nvox)
        map = self.multiplyMask(seld.vectorize(map,self.mask))
        return map

    def multiplyMask(self, img):
        # Returns an image multiplied by the brain mask to remove all values outside the brain
        return np.multiply(self.mask.astype(bool), img)

    def main(self):
        self.fit()
        md, rd, ad, fa, fe, trace, mk, rk, ak = self.extract()
        map = self.findViols([0, 1, 0])
        md = self.multiplyMask(md)
        rd = self.multiplyMask(rd)
        ad = self.multiplyMask(ad)
        fa = self.multiplyMask(fa)
        mk = self.multiplyMask(mk)
        rk = self.multiplyMask(rk)
        ak = self.multiplyMask(ak)
        return map, md, rd, ad, fa, fe, trace, mk, rk, ak

    def detectOutliers(self):
        """
        Uses 100,000 direction in chunks of 10 to iteratively find outliers. Returns a mask of locations where
        :return:
        """
        dir = np.genfromtxt('dirs100000.csv', delimiter=",")
        nvox = self.dt.shape[1]
        akc_out = np.zeros(nvox, dtype=bool)
        N = dir.shape[0]
        nblocks = 10
        inputs = tqdm(range(nblocks))
        print('...computing outliers')
        for i in inputs:
            akc = self.kurtosisCoeff(self.dt, dir[int(N/nblocks*i):int(N/nblocks*(i+1))])
            akc_out[np.where(np.any(np.logical_or(akc < -2, akc > 10), axis=0))] = True
        akc_out = self.multiplyMask(self.vectorize(akc_out, self.mask))
        self.outliers = akc_out
        return akc_out

class medianFilter(object):
    def __init__(self, img, violmask, th=1, sz=3, conn='face'):
        assert th > 0, 'Threshold cannot be zero, disable median filtering instead'
        assert violmask.shape == img.shape, 'Image dimensions not the same as violation mask dimensions'
        self.Threshold = th
        self.Size = sz
        self.Connectivity = conn
        self.Mask = violmask >= th
        self.Img = img

        # Get box filter properties
        centralIdx = np.median(range(sz))
        d2move = np.int(np.abs(sz - (centralIdx + 1))) # Add 1 to central idx because first index starts with zero

        # Apply a nan padding to all 3 dimensions of the input image and a nan padding to mask. Padding widths is same
        # distance between centroid of patch to edge. This enables median filtering of edges.
        self.Img = np.pad(self.Img, d2move, 'constant', constant_values=np.nan)
        self.Mask = np.pad(self.Mask, d2move, 'constant', constant_values=0)

        (Ix, Iy, Iz) = img.shape
        (Mx, My, Mz) = self.Mask.shape

    def findReplacement(self, bias='left'):
        """
        Returns information on replacements for violating voxels

        Usage
        -----
        m = med.findReplacement(bias='rand')

        Parameters
        ----------
        bias: 'left', 'right', or 'rand'
               In the even the number of voxels in patch is even (for median calculation), 'left' will pick a median to
               the left of mean and 'right' will pick a median to the right of mean. 'rand' will randoms pick a bias.

        Returns
        -------
        m: Vector containing index of replacement voxel in patch. In conn = 'face' max is 5 and conn =
        """
        # Get box filter properties
        centralIdx = np.median(range(self.Size))
        d2move = np.int(np.abs(self.Size - (centralIdx + 1)))  # Add 1 to central idx because first index starts with zero

        violIdx = np.array(np.where(self.Mask))   # Locate coordinates of violations
        self.PatchIdx = np.zeros(violIdx.shape[1])

        inputs = tqdm(range(violIdx.shape[1]))
        cntSkip = 0
        for i in inputs:
            # Index beginning and ending of patch
            Ib = violIdx[0, i] - d2move
            Ie = violIdx[0, i] + d2move + 1     # Mitigate Python's [X,Y) indexing
            Jb = violIdx[1, i] - d2move
            Je = violIdx[1, i] + d2move + 1     # Mitigate Python's [X,Y) indexing
            Kb = violIdx[2, i] - d2move
            Ke = violIdx[2, i] + d2move + 1     # Mitigate Python's [X,Y) indexing

            if self.Connectivity == 'all':
                patchViol = np.delete(np.ravel(self.Mask[Ib:Ie, Jb:Je, Kb:Ke]), 13)     # Remove 14th (centroid) element
                patchImg = np.delete(np.ravel(self.Img[Ib:Ie, Jb:Je, Kb:Ke]), 13)            # Remove 14th (centroid) element
                connLimit = 26
            elif self.Connectivity == 'face':
                patchViol = self.Mask[[Ib, Ie], violIdx[1, i], violIdx[2, i]]
                patchViol = np.hstack((patchViol, self.Mask[violIdx[0,i], [Jb, Je], violIdx[2, i]]))
                patchViol = np.hstack((patchViol, self.Mask[violIdx[0, i], violIdx[1, i], [Kb, Ke]]))
                patchImg = self.Img[[Ib, Ie], violIdx[1, i], violIdx[2, i]]
                patchImg = np.hstack((patchImg, self.Img[violIdx[0, i], [Jb, Je], violIdx[2, i]]))
                patchImg = np.hstack((patchImg, self.Img[violIdx[0, i], violIdx[1, i], [Kb, Ke]]))
                connLimit = 6
            else:
                raise Exception('Connectivity choice "{}" is invalid. Please enter either "all" or "face".'.format(self.Connectivity))

            nVoil = np.sum(patchViol)

            # Here a check is performed to compute the number of violations in a patch. If all voxels are violations,
            # do nothing. Otherwise, exclude violation voxels from the median calculation
            if nVoil == connLimit:
                self.PatchIdx[i] = np.nan
                cntSkip = cntSkip + 1
                continue
            else:
                # Sort all patch values in ascending order and remove NaNs
                patchVals = np.array(np.sort(patchImg[~np.isnan(patchImg)],kind='quicksort'))
                nVals = patchVals.size

                # Median algorithm dependent on whether number of valid voxels (nVals) is even or odd
                if np.mod(nVals, 2) == 0:                                       # If even
                    medianIdxTmp = np.array([nVals/2 - 1, nVals/2],dtype=int)   # Convert to Py index (-1)
                    if bias == 'left':
                        medianIdx = medianIdxTmp[0]
                    elif bias == 'right':
                        medianIdx = medianIdxTmp[1]
                    elif bias == 'rand':
                        medianIdx = medianIdxTmp[rnd.randint(0,1)]
                else:                                                           # If odd
                    medianIdx = (nVals-1)/2                                     # Convert to Py index (-1)

                # Now that a the index of a median voxel is located, determine it's value in sorted list and find the
                # location of that voxel in patch. The median index needs to be relative to patch, not sorted list. In
                # the event that there are more than one indexes of the same value, use the first one.
                medianIdxP = np.where(patchImg == patchVals[np.int(medianIdx)])[0][0]
                self.PatchIdx[i] = medianIdxP
        self.PatchIdx = self.PatchIdx.astype(int)   # Convert to integer
        print('%d voxels out of %d were completely surrounded by violations and were ignored' %(cntSkip, violIdx.shape[1]))
        return self.PatchIdx









