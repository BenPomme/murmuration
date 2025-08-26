"""Mock torch module for testing without PyTorch installation."""

import numpy as np
from typing import Any, Optional, List, Tuple
import random


class Tensor:
    """Mock tensor class."""
    
    def __init__(self, data):
        self.data = np.array(data)
        self.grad = None
        self.requires_grad = False
        
    def detach(self):
        return Tensor(self.data)
    
    def cpu(self):
        return self
    
    def numpy(self):
        return self.data
    
    def item(self):
        return float(self.data)
    
    def mean(self):
        return Tensor(np.mean(self.data))
    
    def sum(self, dim=None):
        if dim is None:
            return Tensor(np.sum(self.data))
        else:
            return Tensor(np.sum(self.data, axis=dim))
    
    def backward(self):
        pass
    
    def __repr__(self):
        return f"Tensor({self.data})"
    
    def __add__(self, other):
        if isinstance(other, Tensor):
            return Tensor(self.data + other.data)
        return Tensor(self.data + other)
    
    def __mul__(self, other):
        if isinstance(other, Tensor):
            return Tensor(self.data * other.data)
        return Tensor(self.data * other)
    
    def __sub__(self, other):
        if isinstance(other, Tensor):
            return Tensor(self.data - other.data)
        return Tensor(self.data - other)
    
    def __pow__(self, other):
        if isinstance(other, Tensor):
            return Tensor(self.data ** other.data)
        return Tensor(self.data ** other)
    
    def add_(self, other):
        """In-place addition."""
        if isinstance(other, Tensor):
            self.data += other.data
        else:
            self.data += other
        return self
    
    def zero_(self):
        """Fill with zeros."""
        self.data.fill(0)
        return self
    
    def __getitem__(self, idx):
        return Tensor(self.data[idx])
    
    def copy_(self, other):
        """Copy data from another tensor."""
        if isinstance(other, Tensor):
            self.data = other.data.copy()
        else:
            self.data = np.array(other)
        return self
    
    def unsqueeze(self, dim):
        """Add dimension."""
        return Tensor(np.expand_dims(self.data, dim))
    
    def squeeze(self, dim=None):
        """Remove dimension."""
        return Tensor(np.squeeze(self.data, dim))
    
    def float(self):
        """Convert to float."""
        return Tensor(self.data.astype(np.float32))
    
    def any(self):
        """Check if any element is True."""
        return bool(np.any(self.data))
    
    def numel(self):
        """Number of elements."""
        return int(np.prod(self.data.shape))
    
    @property
    def shape(self):
        return self.data.shape


def tensor(data, dtype=None, requires_grad=False):
    """Create a tensor."""
    t = Tensor(data)
    t.requires_grad = requires_grad
    return t


def zeros(shape):
    """Create zero tensor."""
    return Tensor(np.zeros(shape))


def ones(shape):
    """Create ones tensor."""
    return Tensor(np.ones(shape))


def randn(*shape):
    """Create random normal tensor."""
    return Tensor(np.random.randn(*shape))


def from_numpy(array):
    """Create tensor from numpy array."""
    return Tensor(array)


def isnan(tensor):
    """Check for NaN values."""
    if isinstance(tensor, Tensor):
        return Tensor(np.isnan(tensor.data))
    return np.isnan(tensor)


def isinf(tensor):
    """Check for infinite values."""
    if isinstance(tensor, Tensor):
        return Tensor(np.isinf(tensor.data))
    return np.isinf(tensor)


def equal(tensor1, tensor2):
    """Check if tensors are equal."""
    if isinstance(tensor1, Tensor) and isinstance(tensor2, Tensor):
        return np.array_equal(tensor1.data, tensor2.data)
    return tensor1 == tensor2


def where(condition, x, y):
    """Element-wise selection."""
    if isinstance(condition, Tensor):
        cond_data = condition.data
    else:
        cond_data = condition
    
    if isinstance(x, Tensor):
        x_data = x.data
    else:
        x_data = x
    
    if isinstance(y, Tensor):
        y_data = y.data
    else:
        y_data = y
    
    return Tensor(np.where(cond_data, x_data, y_data))


def normal(mean, std, size, dtype=None):
    """Create normal distributed tensor."""
    return Tensor(np.random.normal(mean, std, size))


def rand_like(tensor):
    """Create random tensor with same shape."""
    if isinstance(tensor, Tensor):
        return Tensor(np.random.rand(*tensor.shape))
    return np.random.rand(*tensor.shape)


def save(obj, path):
    """Mock save function."""
    import pickle
    with open(path, 'wb') as f:
        pickle.dump(obj, f)


def load(path):
    """Mock load function."""
    import pickle
    with open(path, 'rb') as f:
        return pickle.load(f)


def tanh(x):
    """Tanh activation."""
    if isinstance(x, Tensor):
        return Tensor(np.tanh(x.data))
    return np.tanh(x)


def exp(x):
    """Exponential."""
    if isinstance(x, Tensor):
        return Tensor(np.exp(x.data))
    return np.exp(x)


def log(x):
    """Logarithm."""
    if isinstance(x, Tensor):
        return Tensor(np.log(x.data))
    return np.log(x)


def clamp(x, min_val, max_val):
    """Clamp values."""
    if isinstance(x, Tensor):
        return Tensor(np.clip(x.data, min_val, max_val))
    return np.clip(x, min_val, max_val)


def manual_seed(seed):
    """Set random seed."""
    np.random.seed(seed)
    random.seed(seed)


def use_deterministic_algorithms(mode):
    """Mock deterministic algorithms setting."""
    pass


def set_num_threads(n):
    """Mock thread setting."""
    pass


class Parameter:
    """Mock parameter."""
    def __init__(self, data):
        self.data = tensor(data, requires_grad=True)
        
    def __repr__(self):
        return f"Parameter({self.data})"


class Module:
    """Mock Module base class."""
    
    def __init__(self):
        self._parameters = {}
        self._modules = {}
        self.training = True
        
    def parameters(self):
        """Get all parameters."""
        params = []
        for p in self._parameters.values():
            if isinstance(p, Parameter):
                params.append(p.data)
        for m in self._modules.values():
            if isinstance(m, Module):
                params.extend(m.parameters())
        return params
    
    def state_dict(self):
        """Get state dict."""
        state = {}
        for name, p in self._parameters.items():
            if isinstance(p, Parameter):
                state[name] = p.data.data
        for name, m in self._modules.items():
            if isinstance(m, Module):
                m_state = m.state_dict()
                for k, v in m_state.items():
                    state[f"{name}.{k}"] = v
        return state
    
    def load_state_dict(self, state_dict):
        """Load state dict."""
        for name, p in self._parameters.items():
            if name in state_dict:
                p.data.data = state_dict[name]
        for name, m in self._modules.items():
            if isinstance(m, Module):
                m_state = {}
                prefix = f"{name}."
                for k, v in state_dict.items():
                    if k.startswith(prefix):
                        m_state[k[len(prefix):]] = v
                if m_state:
                    m.load_state_dict(m_state)
    
    def train(self, mode=True):
        """Set training mode."""
        self.training = mode
        return self
    
    def eval(self):
        """Set eval mode."""
        return self.train(False)
    
    def zero_grad(self):
        """Zero gradients."""
        for p in self.parameters():
            if hasattr(p, 'grad'):
                p.grad = None
    
    def forward(self, x):
        """Forward pass."""
        raise NotImplementedError
    
    def __call__(self, x):
        """Call forward."""
        return self.forward(x)


class Linear(Module):
    """Mock linear layer."""
    
    def __init__(self, in_features, out_features):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self._parameters['weight'] = Parameter(randn(out_features, in_features).data * 0.1)
        self._parameters['bias'] = Parameter(zeros((out_features,)).data)
    
    def forward(self, x):
        """Forward pass."""
        if isinstance(x, Tensor):
            output = x.data @ self._parameters['weight'].data.data.T + self._parameters['bias'].data.data
            return Tensor(output)
        return x @ self._parameters['weight'].data.data.T + self._parameters['bias'].data.data


class Sequential(Module):
    """Mock sequential container."""
    
    def __init__(self, *layers):
        super().__init__()
        for i, layer in enumerate(layers):
            self._modules[str(i)] = layer
    
    def forward(self, x):
        """Forward pass."""
        for module in self._modules.values():
            x = module(x)
        return x


class Tanh(Module):
    """Mock Tanh activation."""
    
    def forward(self, x):
        return tanh(x)


class Adam:
    """Mock Adam optimizer."""
    
    def __init__(self, params, lr=1e-3):
        self.params = list(params)
        self.lr = lr
    
    def zero_grad(self):
        """Zero gradients."""
        for p in self.params:
            if hasattr(p, 'grad'):
                p.grad = None
    
    def step(self):
        """Optimization step."""
        pass


class Categorical:
    """Mock categorical distribution."""
    
    def __init__(self, probs=None, logits=None):
        if logits is not None:
            if isinstance(logits, Tensor):
                logits_data = logits.data
            else:
                logits_data = logits
            # Softmax
            exp_logits = np.exp(logits_data - np.max(logits_data))
            self.probs = exp_logits / np.sum(exp_logits)
        else:
            self.probs = probs.data if isinstance(probs, Tensor) else probs
    
    def sample(self):
        """Sample from distribution."""
        idx = np.random.choice(len(self.probs), p=self.probs)
        return Tensor([idx])
    
    def log_prob(self, value):
        """Log probability."""
        if isinstance(value, Tensor):
            idx = int(value.data[0])
        else:
            idx = int(value)
        return Tensor([np.log(self.probs[idx] + 1e-8)])
    
    def entropy(self):
        """Entropy."""
        entropy_val = -np.sum(self.probs * np.log(self.probs + 1e-8))
        if np.isscalar(entropy_val):
            return Tensor([entropy_val])
        return Tensor(entropy_val)


class Normal:
    """Mock normal distribution."""
    
    def __init__(self, loc, scale):
        self.loc = loc.data if isinstance(loc, Tensor) else loc
        self.scale = scale.data if isinstance(scale, Tensor) else scale
    
    def sample(self):
        """Sample from distribution."""
        return Tensor(np.random.normal(self.loc, self.scale))
    
    def log_prob(self, value):
        """Log probability."""
        if isinstance(value, Tensor):
            val = value.data
        else:
            val = value
        log_prob_val = -0.5 * ((val - self.loc) / self.scale) ** 2 - np.log(self.scale) - 0.5 * np.log(2 * np.pi)
        return Tensor(log_prob_val)
    
    def entropy(self):
        """Entropy."""
        entropy_val = 0.5 * np.log(2 * np.pi * np.e * self.scale ** 2)
        return Tensor(entropy_val)


# Mock torch.nn module
class nn:
    Module = Module
    Linear = Linear
    Sequential = Sequential
    Tanh = Tanh
    Parameter = Parameter
    
    @staticmethod
    def init_zeros_(tensor):
        if isinstance(tensor, Tensor):
            tensor.data.fill(0)
        return tensor
    
    @staticmethod
    def init_normal_(tensor, mean=0, std=1):
        if isinstance(tensor, Tensor):
            tensor.data = np.random.normal(mean, std, tensor.data.shape)
        return tensor
    
    # Mock utils submodule
    class utils:
        @staticmethod
        def clip_grad_norm_(parameters, max_norm):
            """Mock gradient clipping."""
            # Just return a mock norm value
            return Tensor([0.5])


# Mock torch.optim module
class optim:
    Adam = Adam


# Mock torch.distributions module
class distributions:
    Categorical = Categorical
    Normal = Normal


# Mock torch.cuda module
class cuda:
    @staticmethod
    def is_available():
        return False


# Float32 type
float32 = np.float32


# Mock context manager for no_grad
class no_grad:
    """Context manager for no gradient computation."""
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass


def min(tensor, other=None):
    """Element-wise minimum."""
    if isinstance(tensor, Tensor):
        if other is None:
            return Tensor(np.min(tensor.data))
        elif isinstance(other, Tensor):
            return Tensor(np.minimum(tensor.data, other.data))
        else:
            return Tensor(np.minimum(tensor.data, other))
    return np.minimum(tensor, other) if other is not None else np.min(tensor)


def max(tensor, other=None):
    """Element-wise maximum."""
    if isinstance(tensor, Tensor):
        if other is None:
            return Tensor(np.max(tensor.data))
        elif isinstance(other, Tensor):
            return Tensor(np.maximum(tensor.data, other.data))
        else:
            return Tensor(np.maximum(tensor.data, other))
    return np.maximum(tensor, other) if other is not None else np.max(tensor)