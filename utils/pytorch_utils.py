""" Utilities for general pytorch helpfulness """

import torch
import numpy as np
import torchvision.transforms as transforms
import torch.cuda as cuda

from torch.autograd import Variable, Function



###############################################################################
#                                                                             #
#                                     SAFETY DANCE                            #
#                                                                             #
###############################################################################
# aka things for safer pytorch usage


def cuda_assert(use_cuda):
    assert not (use_cuda and not cuda.is_available())


def safe_var(entity, **kwargs):
    """ Returns a variable of an entity, which may or may not already be a
        variable
    """
    if isinstance(entity, Variable):
        return entity
    elif isinstance(entity, torch.tensor._TensorBase):
        return Variable(entity, **kwargs)
    else:
        raise Exception("Can't cast %s to a Variable" %
                        entity.__class__.__name__)


def safe_tensor(entity):
    """ Returns a tensor of an entity, which may or may not already be a
        tensor
    """
    if isinstance(entity, Variable):
        return entity.data
    elif isinstance(entity, torch.tensor._TensorBase):
        return entity
    elif isinstance(entity, np.ndarray):
        return torch.Tensor(entity) # UNSAFE CUDA CASTING
    else:
        raise Exception("Can't cast %s to a Variable" %
                        entity.__class__.__name__)


##############################################################################
#                                                                            #
#                               CONVENIENCE STORE                            #
#                                                                            #
##############################################################################
# aka convenient things that are not builtin to pytorch

class AverageMeter(object):
    """Computes and stores the average and current value"""
    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count

    def __str__(self):
        return str(self.avg)


def tuple_getter(tensor, idx_tuple):
    """ access a tensor by a tuple """
    tensor_ = tensor
    for el in idx_tuple:
        tensor_ = tensor_[el]
    return tensor_


def tuple_setter(tensor, idx_tuple, val):
    """ Sets a tensor element while indexing by a tuple"""

    tensor_ = tensor
    for el in idx_tuple[:-1]:
        tensor_ = tensor_[el]

    tensor_[idx_tuple[-1]] = val
    return tensor


def torch_argmax(tensor):
    """ Returns the idx tuple that corresponds to the max value in the tensor"""

    flat_tensor = tensor.view(tensor.numel())
    _, argmax = flat_tensor.max(0)
    return np.unravel_index(int(argmax), tensor.shape)


def torch_argmin(tensor):
    """ Returns the idx tuple that corresponds to the min value in the tensor"""
    flat_tensor = tensor.view(tensor.numel())
    _, argmin = flat_tensor.min(0)
    return np.unravel_index(int(argmin), tensor.shape)


def clamp_ref(x, y, l_inf):
    """ Clamps each element of x to be within l_inf of each element of y """
    return torch.clamp(x - y , -l_inf, l_inf) + y


def torch_arctanh(x, eps=1e-6):
    x *= (1. - eps)
    return (torch.log((1 + x) / (1 - x))) * 0.5


def tanh_rescale(x, x_min=-1., x_max=1.):
    return (torch.tanh(x) + 1) * 0.5 * (x_max - x_min) + x_min


##############################################################################
#                                                                            #
#                               CLASSIFICATION HELPERS                       #
#                                                                            #
##############################################################################
# aka little utils that are useful for classification

def accuracy_int(output, target, topk=1):
    """ Computes the number of correct examples in the output.
    RETURNS an int!
    """
    _, pred = output.topk(topk, 1, True, True)
    pred = pred.t()
    correct = pred.eq(target.view(1, -1).expand_as(pred))
    return int(correct.data.sum())


def accuracy(output, target, topk=(1,)):
    """Computes the precision@k for the specified values of k"""
    maxk = max(topk)
    batch_size = target.size(0)

    _, pred = output.topk(maxk, 1, True, True)
    pred = pred.t()
    correct = pred.eq(target.view(1, -1).expand_as(pred))

    res = []
    for k in topk:
        correct_k = correct[:k].view(-1).float().sum(0)
        res.append(correct_k.mul_(100.0 / batch_size))
    return res



###############################################################################
#                                                                             #
#                                   NORMALIZERS                               #
#                                                                             #
###############################################################################


class IdentityNormalize(object):
    def __init__(self):
        pass

    def forward(self, var):
        return var


class DifferentiableNormalize(Function):

    def __init__(self, mean, std):
        super(DifferentiableNormalize, self).__init__()
        self.mean = mean
        self.std = std
        self.differentiable = True
        self.nondiff_normer = transforms.Normalize(mean, std)


    def __call__(self, var):
        if self.differentiable:
            return self.forward(var)
        else:
            return self.nondiff_normer(var)


    def _setter(self, c, mean, std):
        """ Modifies params going forward """
        if mean is not None:
            self.mean = mean
        assert len(self.mean) == c

        if std is not None:
            self.std = std
        assert len(self.std) == c

        if mean is not None or std is not None:
            self.nondiff_normer = transforms.Normalize(self.mean, self.std)


    def differentiable_call(self):
        """ Sets the __call__ method to be the differentiable version """
        self.differentiable = True


    def nondifferentiable_call(self):
        """ Sets the __call__ method to be the torchvision.transforms version"""
        self.differentiable = False


    def forward(self, var, mean=None, std=None):
        """ Normalizes var by subtracting the mean of each channel and then
            dividing each channel by standard dev
        ARGS:
            self - stores mean and std for later
            var - Variable of shape NxCxHxW
            mean - if not None is a list of length C for channel-means
            std - if not None is a list of length C for channel-stds
        RETURNS:
            variable of normalized var
        """
        c = var.shape[1]
        self._setter(c, mean, std)

        mean_var = Variable(var.data.new(self.mean).view(1, c, 1, 1))
        std_var = Variable(var.data.new(self.std).view(1, c, 1, 1))
        return (var - mean_var) / std_var



