import numpy as np
import pytest
from scipy.stats import (bootstrap, BootstrapDegenerateDistributionWarning,
                         monte_carlo_test, permutation_test)
from numpy.testing import assert_allclose, assert_equal, suppress_warnings
from scipy import stats
from scipy import special
from .. import _resampling as _resampling
from scipy._lib._util import rng_integers
from scipy.optimize import root


def test_bootstrap_iv():

    message = "`data` must be a sequence of samples."
    with pytest.raises(ValueError, match=message):
        bootstrap(1, np.mean)

    message = "`data` must contain at least one sample."
    with pytest.raises(ValueError, match=message):
        bootstrap(tuple(), np.mean)

    message = "each sample in `data` must contain two or more observations..."
    with pytest.raises(ValueError, match=message):
        bootstrap(([1, 2, 3], [1]), np.mean)

    message = ("When `paired is True`, all samples must have the same length ")
    with pytest.raises(ValueError, match=message):
        bootstrap(([1, 2, 3], [1, 2, 3, 4]), np.mean, paired=True)

    message = "`vectorized` must be `True` or `False`."
    with pytest.raises(ValueError, match=message):
        bootstrap(1, np.mean, vectorized='ekki')

    message = "`axis` must be an integer."
    with pytest.raises(ValueError, match=message):
        bootstrap(([1, 2, 3],), np.mean, axis=1.5)

    message = "could not convert string to float"
    with pytest.raises(ValueError, match=message):
        bootstrap(([1, 2, 3],), np.mean, confidence_level='ni')

    message = "`n_resamples` must be a positive integer."
    with pytest.raises(ValueError, match=message):
        bootstrap(([1, 2, 3],), np.mean, n_resamples=-1000)

    message = "`n_resamples` must be a positive integer."
    with pytest.raises(ValueError, match=message):
        bootstrap(([1, 2, 3],), np.mean, n_resamples=1000.5)

    message = "`batch` must be a positive integer or None."
    with pytest.raises(ValueError, match=message):
        bootstrap(([1, 2, 3],), np.mean, batch=-1000)

    message = "`batch` must be a positive integer or None."
    with pytest.raises(ValueError, match=message):
        bootstrap(([1, 2, 3],), np.mean, batch=1000.5)

    message = "`method` must be in"
    with pytest.raises(ValueError, match=message):
        bootstrap(([1, 2, 3],), np.mean, method='ekki')

    message = "`method = 'BCa' is only available for one-sample statistics"

    def statistic(x, y, axis):
        mean1 = np.mean(x, axis)
        mean2 = np.mean(y, axis)
        return mean1 - mean2

    with pytest.raises(ValueError, match=message):
        bootstrap(([.1, .2, .3], [.1, .2, .3]), statistic, method='BCa')

    message = "'herring' cannot be used to seed a"
    with pytest.raises(ValueError, match=message):
        bootstrap(([1, 2, 3],), np.mean, random_state='herring')


@pytest.mark.parametrize("method", ['basic', 'percentile', 'BCa'])
@pytest.mark.parametrize("axis", [0, 1, 2])
def test_bootstrap_batch(method, axis):
    # for one-sample statistics, batch size shouldn't affect the result
    np.random.seed(0)

    x = np.random.rand(10, 11, 12)
    res1 = bootstrap((x,), np.mean, batch=None, method=method,
                     random_state=0, axis=axis, n_resamples=100)
    res2 = bootstrap((x,), np.mean, batch=10, method=method,
                     random_state=0, axis=axis, n_resamples=100)

    assert_equal(res2.confidence_interval.low, res1.confidence_interval.low)
    assert_equal(res2.confidence_interval.high, res1.confidence_interval.high)
    assert_equal(res2.standard_error, res1.standard_error)


@pytest.mark.parametrize("method", ['basic', 'percentile', 'BCa'])
def test_bootstrap_paired(method):
    # test that `paired` works as expected
    np.random.seed(0)
    n = 100
    x = np.random.rand(n)
    y = np.random.rand(n)

    def my_statistic(x, y, axis=-1):
        return ((x-y)**2).mean(axis=axis)

    def my_paired_statistic(i, axis=-1):
        a = x[i]
        b = y[i]
        res = my_statistic(a, b)
        return res

    i = np.arange(len(x))

    res1 = bootstrap((i,), my_paired_statistic, random_state=0)
    res2 = bootstrap((x, y), my_statistic, paired=True, random_state=0)

    assert_allclose(res1.confidence_interval, res2.confidence_interval)
    assert_allclose(res1.standard_error, res2.standard_error)


@pytest.mark.parametrize("method", ['basic', 'percentile', 'BCa'])
@pytest.mark.parametrize("axis", [0, 1, 2])
@pytest.mark.parametrize("paired", [True, False])
def test_bootstrap_vectorized(method, axis, paired):
    # test that paired is vectorized as expected: when samples are tiled,
    # CI and standard_error of each axis-slice is the same as those of the
    # original 1d sample

    if not paired and method == 'BCa':
        # should re-assess when BCa is extended
        pytest.xfail(reason="BCa currently for 1-sample statistics only")
    np.random.seed(0)

    def my_statistic(x, y, z, axis=-1):
        return x.mean(axis=axis) + y.mean(axis=axis) + z.mean(axis=axis)

    shape = 10, 11, 12
    n_samples = shape[axis]

    x = np.random.rand(n_samples)
    y = np.random.rand(n_samples)
    z = np.random.rand(n_samples)
    res1 = bootstrap((x, y, z), my_statistic, paired=paired, method=method,
                     random_state=0, axis=0, n_resamples=100)

    reshape = [1, 1, 1]
    reshape[axis] = n_samples
    x = np.broadcast_to(x.reshape(reshape), shape)
    y = np.broadcast_to(y.reshape(reshape), shape)
    z = np.broadcast_to(z.reshape(reshape), shape)
    res2 = bootstrap((x, y, z), my_statistic, paired=paired, method=method,
                     random_state=0, axis=axis, n_resamples=100)

    assert_allclose(res2.confidence_interval.low,
                    res1.confidence_interval.low)
    assert_allclose(res2.confidence_interval.high,
                    res1.confidence_interval.high)
    assert_allclose(res2.standard_error, res1.standard_error)

    result_shape = list(shape)
    result_shape.pop(axis)

    assert_equal(res2.confidence_interval.low.shape, result_shape)
    assert_equal(res2.confidence_interval.high.shape, result_shape)
    assert_equal(res2.standard_error.shape, result_shape)


@pytest.mark.parametrize("method", ['basic', 'percentile', 'BCa'])
def test_bootstrap_against_theory(method):
    # based on https://www.statology.org/confidence-intervals-python/
    data = stats.norm.rvs(loc=5, scale=2, size=5000, random_state=0)
    alpha = 0.95
    dist = stats.t(df=len(data)-1, loc=np.mean(data), scale=stats.sem(data))
    expected_interval = dist.interval(confidence=alpha)
    expected_se = dist.std()

    res = bootstrap((data,), np.mean, n_resamples=5000,
                    confidence_level=alpha, method=method,
                    random_state=0)
    assert_allclose(res.confidence_interval, expected_interval, rtol=5e-4)
    assert_allclose(res.standard_error, expected_se, atol=3e-4)


tests_R = {"basic": (23.77, 79.12),
           "percentile": (28.86, 84.21),
           "BCa": (32.31, 91.43)}


@pytest.mark.parametrize("method, expected", tests_R.items())
def test_bootstrap_against_R(method, expected):
    # Compare against R's "boot" library
    # library(boot)

    # stat <- function (x, a) {
    #     mean(x[a])
    # }

    # x <- c(10, 12, 12.5, 12.5, 13.9, 15, 21, 22,
    #        23, 34, 50, 81, 89, 121, 134, 213)

    # # Use a large value so we get a few significant digits for the CI.
    # n = 1000000
    # bootresult = boot(x, stat, n)
    # result <- boot.ci(bootresult)
    # print(result)
    x = np.array([10, 12, 12.5, 12.5, 13.9, 15, 21, 22,
                  23, 34, 50, 81, 89, 121, 134, 213])
    res = bootstrap((x,), np.mean, n_resamples=1000000, method=method,
                    random_state=0)
    assert_allclose(res.confidence_interval, expected, rtol=0.005)


tests_against_itself_1samp = {"basic": 1780,
                              "percentile": 1784,
                              "BCa": 1784}


@pytest.mark.parametrize("method, expected",
                         tests_against_itself_1samp.items())
def test_bootstrap_against_itself_1samp(method, expected):
    # The expected values in this test were generated using bootstrap
    # to check for unintended changes in behavior. The test also makes sure
    # that bootstrap works with multi-sample statistics and that the
    # `axis` argument works as expected / function is vectorized.
    np.random.seed(0)

    n = 100  # size of sample
    n_resamples = 999  # number of bootstrap resamples used to form each CI
    confidence_level = 0.9

    # The true mean is 5
    dist = stats.norm(loc=5, scale=1)
    stat_true = dist.mean()

    # Do the same thing 2000 times. (The code is fully vectorized.)
    n_replications = 2000
    data = dist.rvs(size=(n_replications, n))
    res = bootstrap((data,),
                    statistic=np.mean,
                    confidence_level=confidence_level,
                    n_resamples=n_resamples,
                    batch=50,
                    method=method,
                    axis=-1)
    ci = res.confidence_interval

    # ci contains vectors of lower and upper confidence interval bounds
    ci_contains_true = np.sum((ci[0] < stat_true) & (stat_true < ci[1]))
    assert ci_contains_true == expected

    # ci_contains_true is not inconsistent with confidence_level
    pvalue = stats.binomtest(ci_contains_true, n_replications,
                             confidence_level).pvalue
    assert pvalue > 0.1


tests_against_itself_2samp = {"basic": 892,
                              "percentile": 890}


@pytest.mark.parametrize("method, expected",
                         tests_against_itself_2samp.items())
def test_bootstrap_against_itself_2samp(method, expected):
    # The expected values in this test were generated using bootstrap
    # to check for unintended changes in behavior. The test also makes sure
    # that bootstrap works with multi-sample statistics and that the
    # `axis` argument works as expected / function is vectorized.
    np.random.seed(0)

    n1 = 100  # size of sample 1
    n2 = 120  # size of sample 2
    n_resamples = 999  # number of bootstrap resamples used to form each CI
    confidence_level = 0.9

    # The statistic we're interested in is the difference in means
    def my_stat(data1, data2, axis=-1):
        mean1 = np.mean(data1, axis=axis)
        mean2 = np.mean(data2, axis=axis)
        return mean1 - mean2

    # The true difference in the means is -0.1
    dist1 = stats.norm(loc=0, scale=1)
    dist2 = stats.norm(loc=0.1, scale=1)
    stat_true = dist1.mean() - dist2.mean()

    # Do the same thing 1000 times. (The code is fully vectorized.)
    n_replications = 1000
    data1 = dist1.rvs(size=(n_replications, n1))
    data2 = dist2.rvs(size=(n_replications, n2))
    res = bootstrap((data1, data2),
                    statistic=my_stat,
                    confidence_level=confidence_level,
                    n_resamples=n_resamples,
                    batch=50,
                    method=method,
                    axis=-1)
    ci = res.confidence_interval

    # ci contains vectors of lower and upper confidence interval bounds
    ci_contains_true = np.sum((ci[0] < stat_true) & (stat_true < ci[1]))
    assert ci_contains_true == expected

    # ci_contains_true is not inconsistent with confidence_level
    pvalue = stats.binomtest(ci_contains_true, n_replications,
                             confidence_level).pvalue
    assert pvalue > 0.1


@pytest.mark.parametrize("method", ["basic", "percentile"])
@pytest.mark.parametrize("axis", [0, 1])
def test_bootstrap_vectorized_3samp(method, axis):
    def statistic(*data, axis=0):
        # an arbitrary, vectorized statistic
        return sum((sample.mean(axis) for sample in data))

    def statistic_1d(*data):
        # the same statistic, not vectorized
        for sample in data:
            assert sample.ndim == 1
        return statistic(*data, axis=0)

    np.random.seed(0)
    x = np.random.rand(4, 5)
    y = np.random.rand(4, 5)
    z = np.random.rand(4, 5)
    res1 = bootstrap((x, y, z), statistic, vectorized=True,
                     axis=axis, n_resamples=100, method=method, random_state=0)
    res2 = bootstrap((x, y, z), statistic_1d, vectorized=False,
                     axis=axis, n_resamples=100, method=method, random_state=0)
    assert_allclose(res1.confidence_interval, res2.confidence_interval)
    assert_allclose(res1.standard_error, res2.standard_error)


@pytest.mark.xfail_on_32bit("Failure is not concerning; see gh-14107")
@pytest.mark.parametrize("method", ["basic", "percentile", "BCa"])
@pytest.mark.parametrize("axis", [0, 1])
def test_bootstrap_vectorized_1samp(method, axis):
    def statistic(x, axis=0):
        # an arbitrary, vectorized statistic
        return x.mean(axis=axis)

    def statistic_1d(x):
        # the same statistic, not vectorized
        assert x.ndim == 1
        return statistic(x, axis=0)

    np.random.seed(0)
    x = np.random.rand(4, 5)
    res1 = bootstrap((x,), statistic, vectorized=True, axis=axis,
                     n_resamples=100, batch=None, method=method,
                     random_state=0)
    res2 = bootstrap((x,), statistic_1d, vectorized=False, axis=axis,
                     n_resamples=100, batch=10, method=method,
                     random_state=0)
    assert_allclose(res1.confidence_interval, res2.confidence_interval)
    assert_allclose(res1.standard_error, res2.standard_error)


@pytest.mark.parametrize("method", ["basic", "percentile", "BCa"])
def test_bootstrap_degenerate(method):
    data = 35 * [10000.]
    if method == "BCa":
        with np.errstate(invalid='ignore'):
            with pytest.warns(BootstrapDegenerateDistributionWarning):
                res = bootstrap([data, ], np.mean, method=method)
                assert_equal(res.confidence_interval, (np.nan, np.nan))
    else:
        res = bootstrap([data, ], np.mean, method=method)
        assert_equal(res.confidence_interval, (10000., 10000.))
    assert_equal(res.standard_error, 0)


@pytest.mark.parametrize("method", ["basic", "percentile", "BCa"])
def test_bootstrap_gh15678(method):
    # Check that gh-15678 is fixed: when statistic function returned a Python
    # float, method="BCa" failed when trying to add a dimension to the float
    rng = np.random.default_rng(354645618886684)
    dist = stats.norm(loc=2, scale=4)
    data = dist.rvs(size=100, random_state=rng)
    data = (data,)
    res = bootstrap(data, stats.skew, method=method, n_resamples=100,
                    random_state=np.random.default_rng(9563))
    # this always worked because np.apply_along_axis returns NumPy data type
    ref = bootstrap(data, stats.skew, method=method, n_resamples=100,
                    random_state=np.random.default_rng(9563), vectorized=False)
    assert_allclose(res.confidence_interval, ref.confidence_interval)
    assert_allclose(res.standard_error, ref.standard_error)
    assert isinstance(res.standard_error, np.float64)


def test_jackknife_resample():
    shape = 3, 4, 5, 6
    np.random.seed(0)
    x = np.random.rand(*shape)
    y = next(_resampling._jackknife_resample(x))

    for i in range(shape[-1]):
        # each resample is indexed along second to last axis
        # (last axis is the one the statistic will be taken over / consumed)
        slc = y[..., i, :]
        expected = np.delete(x, i, axis=-1)

        assert np.array_equal(slc, expected)

    y2 = np.concatenate(list(_resampling._jackknife_resample(x, batch=2)),
                        axis=-2)
    assert np.array_equal(y2, y)


@pytest.mark.parametrize("rng_name", ["RandomState", "default_rng"])
def test_bootstrap_resample(rng_name):
    rng = getattr(np.random, rng_name, None)
    if rng is None:
        pytest.skip(f"{rng_name} not available.")
    rng1 = rng(0)
    rng2 = rng(0)

    n_resamples = 10
    shape = 3, 4, 5, 6

    np.random.seed(0)
    x = np.random.rand(*shape)
    y = _resampling._bootstrap_resample(x, n_resamples, random_state=rng1)

    for i in range(n_resamples):
        # each resample is indexed along second to last axis
        # (last axis is the one the statistic will be taken over / consumed)
        slc = y[..., i, :]

        js = rng_integers(rng2, 0, shape[-1], shape[-1])
        expected = x[..., js]

        assert np.array_equal(slc, expected)


@pytest.mark.parametrize("score", [0, 0.5, 1])
@pytest.mark.parametrize("axis", [0, 1, 2])
def test_percentile_of_score(score, axis):
    shape = 10, 20, 30
    np.random.seed(0)
    x = np.random.rand(*shape)
    p = _resampling._percentile_of_score(x, score, axis=-1)

    def vectorized_pos(a, score, axis):
        return np.apply_along_axis(stats.percentileofscore, axis, a, score)

    p2 = vectorized_pos(x, score, axis=-1)/100

    assert_allclose(p, p2, 1e-15)


def test_percentile_along_axis():
    # the difference between _percentile_along_axis and np.percentile is that
    # np.percentile gets _all_ the qs for each axis slice, whereas
    # _percentile_along_axis gets the q corresponding with each axis slice

    shape = 10, 20
    np.random.seed(0)
    x = np.random.rand(*shape)
    q = np.random.rand(*shape[:-1]) * 100
    y = _resampling._percentile_along_axis(x, q)

    for i in range(shape[0]):
        res = y[i]
        expected = np.percentile(x[i], q[i], axis=-1)
        assert_allclose(res, expected, 1e-15)


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_vectorize_statistic(axis):
    # test that _vectorize_statistic vectorizes a statistic along `axis`

    def statistic(*data, axis):
        # an arbitrary, vectorized statistic
        return sum((sample.mean(axis) for sample in data))

    def statistic_1d(*data):
        # the same statistic, not vectorized
        for sample in data:
            assert sample.ndim == 1
        return statistic(*data, axis=0)

    # vectorize the non-vectorized statistic
    statistic2 = _resampling._vectorize_statistic(statistic_1d)

    np.random.seed(0)
    x = np.random.rand(4, 5, 6)
    y = np.random.rand(4, 1, 6)
    z = np.random.rand(1, 5, 6)

    res1 = statistic(x, y, z, axis=axis)
    res2 = statistic2(x, y, z, axis=axis)
    assert_allclose(res1, res2)


@pytest.mark.xslow()
@pytest.mark.parametrize("method", ["basic", "percentile", "BCa"])
def test_vector_valued_statistic(method):
    # Generate 95% confidence interval around MLE of normal distribution
    # parameters. Repeat 100 times, each time on sample of size 100.
    # Check that confidence interval contains true parameters ~95 times.
    # Confidence intervals are estimated and stochastic; a test failure
    # does not necessarily indicate that something is wrong. More important
    # than values of `counts` below is that the shapes of the outputs are
    # correct.

    rng = np.random.default_rng(2196847219)
    params = 1, 0.5
    sample = stats.norm.rvs(*params, size=(100, 100), random_state=rng)

    def statistic(data):
        return stats.norm.fit(data)

    res = bootstrap((sample,), statistic, method=method, axis=-1,
                    vectorized=False)

    counts = np.sum((res.confidence_interval.low.T < params)
                    & (res.confidence_interval.high.T > params),
                    axis=0)
    assert np.all(counts >= 90)
    assert np.all(counts <= 100)
    assert res.confidence_interval.low.shape == (2, 100)
    assert res.confidence_interval.high.shape == (2, 100)
    assert res.standard_error.shape == (2, 100)


# --- Test Monte Carlo Hypothesis Test --- #

class TestMonteCarloHypothesisTest:
    atol = 2.5e-2  # for comparing p-value

    def rvs(self, rvs_in, rs):
        return lambda *args, **kwds: rvs_in(*args, random_state=rs, **kwds)

    def test_input_validation(self):
        # test that the appropriate error messages are raised for invalid input

        def stat(x):
            return stats.skewnorm(x).statistic

        message = "`axis` must be an integer."
        with pytest.raises(ValueError, match=message):
            monte_carlo_test([1, 2, 3], stats.norm.rvs, stat, axis=1.5)

        message = "`vectorized` must be `True` or `False`."
        with pytest.raises(ValueError, match=message):
            monte_carlo_test([1, 2, 3], stats.norm.rvs, stat, vectorized=1.5)

        message = "`rvs` must be callable."
        with pytest.raises(TypeError, match=message):
            monte_carlo_test([1, 2, 3], None, stat)

        message = "`statistic` must be callable."
        with pytest.raises(TypeError, match=message):
            monte_carlo_test([1, 2, 3], stats.norm.rvs, None)

        message = "`n_resamples` must be a positive integer."
        with pytest.raises(ValueError, match=message):
            monte_carlo_test([1, 2, 3], stats.norm.rvs, stat,
                             n_resamples=-1000)

        message = "`n_resamples` must be a positive integer."
        with pytest.raises(ValueError, match=message):
            monte_carlo_test([1, 2, 3], stats.norm.rvs, stat,
                             n_resamples=1000.5)

        message = "`batch` must be a positive integer or None."
        with pytest.raises(ValueError, match=message):
            monte_carlo_test([1, 2, 3], stats.norm.rvs, stat, batch=-1000)

        message = "`batch` must be a positive integer or None."
        with pytest.raises(ValueError, match=message):
            monte_carlo_test([1, 2, 3], stats.norm.rvs, stat, batch=1000.5)

        message = "`alternative` must be in..."
        with pytest.raises(ValueError, match=message):
            monte_carlo_test([1, 2, 3], stats.norm.rvs, stat,
                             alternative='ekki')

    def test_batch(self):
        # make sure that the `batch` parameter is respected by checking the
        # maximum batch size provided in calls to `statistic`
        rng = np.random.default_rng(23492340193)
        x = rng.random(10)

        def statistic(x, axis):
            batch_size = 1 if x.ndim == 1 else len(x)
            statistic.batch_size = max(batch_size, statistic.batch_size)
            statistic.counter += 1
            return stats.skewtest(x, axis=axis).statistic
        statistic.counter = 0
        statistic.batch_size = 0

        kwds = {'sample': x, 'statistic': statistic,
                'n_resamples': 1000, 'vectorized': True}

        kwds['rvs'] = self.rvs(stats.norm.rvs, np.random.default_rng(32842398))
        res1 = monte_carlo_test(batch=1, **kwds)
        assert_equal(statistic.counter, 1001)
        assert_equal(statistic.batch_size, 1)

        kwds['rvs'] = self.rvs(stats.norm.rvs, np.random.default_rng(32842398))
        statistic.counter = 0
        res2 = monte_carlo_test(batch=50, **kwds)
        assert_equal(statistic.counter, 21)
        assert_equal(statistic.batch_size, 50)

        kwds['rvs'] = self.rvs(stats.norm.rvs, np.random.default_rng(32842398))
        statistic.counter = 0
        res3 = monte_carlo_test(**kwds)
        assert_equal(statistic.counter, 2)
        assert_equal(statistic.batch_size, 1000)

        assert_equal(res1.pvalue, res3.pvalue)
        assert_equal(res2.pvalue, res3.pvalue)

    @pytest.mark.parametrize('axis', range(-3, 3))
    def test_axis(self, axis):
        # test that Nd-array samples are handled correctly for valid values
        # of the `axis` parameter
        rng = np.random.default_rng(2389234)
        norm_rvs = self.rvs(stats.norm.rvs, rng)

        size = [2, 3, 4]
        size[axis] = 100
        x = norm_rvs(size=size)
        expected = stats.skewtest(x, axis=axis)

        def statistic(x, axis):
            return stats.skewtest(x, axis=axis).statistic

        res = monte_carlo_test(x, norm_rvs, statistic, vectorized=True,
                               n_resamples=20000, axis=axis)

        assert_allclose(res.statistic, expected.statistic)
        assert_allclose(res.pvalue, expected.pvalue, atol=self.atol)

    @pytest.mark.parametrize('alternative', ("less", "greater"))
    @pytest.mark.parametrize('a', np.linspace(-0.5, 0.5, 5))  # skewness
    def test_against_ks_1samp(self, alternative, a):
        # test that monte_carlo_test can reproduce pvalue of ks_1samp
        rng = np.random.default_rng(65723433)

        x = stats.skewnorm.rvs(a=a, size=30, random_state=rng)
        expected = stats.ks_1samp(x, stats.norm.cdf, alternative=alternative)

        def statistic1d(x):
            return stats.ks_1samp(x, stats.norm.cdf, mode='asymp',
                                  alternative=alternative).statistic

        norm_rvs = self.rvs(stats.norm.rvs, rng)
        res = monte_carlo_test(x, norm_rvs, statistic1d,
                               n_resamples=1000, vectorized=False,
                               alternative=alternative)

        assert_allclose(res.statistic, expected.statistic)
        if alternative == 'greater':
            assert_allclose(res.pvalue, expected.pvalue, atol=self.atol)
        elif alternative == 'less':
            assert_allclose(1-res.pvalue, expected.pvalue, atol=self.atol)

    @pytest.mark.parametrize('hypotest', (stats.skewtest, stats.kurtosistest))
    @pytest.mark.parametrize('alternative', ("less", "greater", "two-sided"))
    @pytest.mark.parametrize('a', np.linspace(-2, 2, 5))  # skewness
    def test_against_normality_tests(self, hypotest, alternative, a):
        # test that monte_carlo_test can reproduce pvalue of normality tests
        rng = np.random.default_rng(85723405)

        x = stats.skewnorm.rvs(a=a, size=150, random_state=rng)
        expected = hypotest(x, alternative=alternative)

        def statistic(x, axis):
            return hypotest(x, axis=axis).statistic

        norm_rvs = self.rvs(stats.norm.rvs, rng)
        res = monte_carlo_test(x, norm_rvs, statistic, vectorized=True,
                               alternative=alternative)

        assert_allclose(res.statistic, expected.statistic)
        assert_allclose(res.pvalue, expected.pvalue, atol=self.atol)

    @pytest.mark.parametrize('a', np.arange(-2, 3))  # skewness parameter
    def test_against_normaltest(self, a):
        # test that monte_carlo_test can reproduce pvalue of normaltest
        rng = np.random.default_rng(12340513)

        x = stats.skewnorm.rvs(a=a, size=150, random_state=rng)
        expected = stats.normaltest(x)

        def statistic(x, axis):
            return stats.normaltest(x, axis=axis).statistic

        norm_rvs = self.rvs(stats.norm.rvs, rng)
        res = monte_carlo_test(x, norm_rvs, statistic, vectorized=True,
                               alternative='greater')

        assert_allclose(res.statistic, expected.statistic)
        assert_allclose(res.pvalue, expected.pvalue, atol=self.atol)

    @pytest.mark.parametrize('a', np.linspace(-0.5, 0.5, 5))  # skewness
    def test_against_cramervonmises(self, a):
        # test that monte_carlo_test can reproduce pvalue of cramervonmises
        rng = np.random.default_rng(234874135)

        x = stats.skewnorm.rvs(a=a, size=30, random_state=rng)
        expected = stats.cramervonmises(x, stats.norm.cdf)

        def statistic1d(x):
            return stats.cramervonmises(x, stats.norm.cdf).statistic

        norm_rvs = self.rvs(stats.norm.rvs, rng)
        res = monte_carlo_test(x, norm_rvs, statistic1d,
                               n_resamples=1000, vectorized=False,
                               alternative='greater')

        assert_allclose(res.statistic, expected.statistic)
        assert_allclose(res.pvalue, expected.pvalue, atol=self.atol)

    @pytest.mark.parametrize('dist_name', ('norm', 'logistic'))
    @pytest.mark.parametrize('i', range(5))
    def test_against_anderson(self, dist_name, i):
        # test that monte_carlo_test can reproduce results of `anderson`. Note:
        # `anderson` does not provide a p-value; it provides a list of
        # significance levels and the associated critical value of the test
        # statistic. `i` used to index this list.

        # find the skewness for which the sample statistic matches one of the
        # critical values provided by `stats.anderson`

        def fun(a):
            rng = np.random.default_rng(394295467)
            x = stats.tukeylambda.rvs(a, size=100, random_state=rng)
            expected = stats.anderson(x, dist_name)
            return expected.statistic - expected.critical_values[i]
        with suppress_warnings() as sup:
            sup.filter(RuntimeWarning)
            sol = root(fun, x0=0)
        assert(sol.success)

        # get the significance level (p-value) associated with that critical
        # value
        a = sol.x[0]
        rng = np.random.default_rng(394295467)
        x = stats.tukeylambda.rvs(a, size=100, random_state=rng)
        expected = stats.anderson(x, dist_name)
        expected_stat = expected.statistic
        expected_p = expected.significance_level[i]/100

        # perform equivalent Monte Carlo test and compare results
        def statistic1d(x):
            return stats.anderson(x, dist_name).statistic

        dist_rvs = self.rvs(getattr(stats, dist_name).rvs, rng)
        with suppress_warnings() as sup:
            sup.filter(RuntimeWarning)
            res = monte_carlo_test(x, dist_rvs,
                                   statistic1d, n_resamples=1000,
                                   vectorized=False, alternative='greater')

        assert_allclose(res.statistic, expected_stat)
        assert_allclose(res.pvalue, expected_p, atol=2*self.atol)


class TestPermutationTest:

    rtol = 1e-14

    # -- Input validation -- #

    def test_permutation_test_iv(self):

        def stat(x, y, axis):
            return stats.ttest_ind((x, y), axis).statistic

        message = "each sample in `data` must contain two or more ..."
        with pytest.raises(ValueError, match=message):
            permutation_test(([1, 2, 3], [1]), stat)

        message = "`data` must be a tuple containing at least two samples"
        with pytest.raises(ValueError, match=message):
            permutation_test((1,), stat)
        with pytest.raises(TypeError, match=message):
            permutation_test(1, stat)

        message = "`axis` must be an integer."
        with pytest.raises(ValueError, match=message):
            permutation_test(([1, 2, 3], [1, 2, 3]), stat, axis=1.5)

        message = "`permutation_type` must be in..."
        with pytest.raises(ValueError, match=message):
            permutation_test(([1, 2, 3], [1, 2, 3]), stat,
                             permutation_type="ekki")

        message = "`vectorized` must be `True` or `False`."
        with pytest.raises(ValueError, match=message):
            permutation_test(([1, 2, 3], [1, 2, 3]), stat, vectorized=1.5)

        message = "`n_resamples` must be a positive integer."
        with pytest.raises(ValueError, match=message):
            permutation_test(([1, 2, 3], [1, 2, 3]), stat, n_resamples=-1000)

        message = "`n_resamples` must be a positive integer."
        with pytest.raises(ValueError, match=message):
            permutation_test(([1, 2, 3], [1, 2, 3]), stat, n_resamples=1000.5)

        message = "`batch` must be a positive integer or None."
        with pytest.raises(ValueError, match=message):
            permutation_test(([1, 2, 3], [1, 2, 3]), stat, batch=-1000)

        message = "`batch` must be a positive integer or None."
        with pytest.raises(ValueError, match=message):
            permutation_test(([1, 2, 3], [1, 2, 3]), stat, batch=1000.5)

        message = "`alternative` must be in..."
        with pytest.raises(ValueError, match=message):
            permutation_test(([1, 2, 3], [1, 2, 3]), stat, alternative='ekki')

        message = "'herring' cannot be used to seed a"
        with pytest.raises(ValueError, match=message):
            permutation_test(([1, 2, 3], [1, 2, 3]), stat,
                             random_state='herring')

    # -- Test Parameters -- #
    @pytest.mark.parametrize('permutation_type',
                             ['pairings', 'samples', 'independent'])
    def test_batch(self, permutation_type):
        # make sure that the `batch` parameter is respected by checking the
        # maximum batch size provided in calls to `statistic`
        np.random.seed(0)
        x = np.random.rand(10)
        y = np.random.rand(10)

        def statistic(x, y, axis):
            batch_size = 1 if x.ndim == 1 else len(x)
            statistic.batch_size = max(batch_size, statistic.batch_size)
            statistic.counter += 1
            return np.mean(x, axis=axis) - np.mean(y, axis=axis)
        statistic.counter = 0
        statistic.batch_size = 0

        kwds = {'n_resamples': 1000, 'permutation_type': permutation_type,
                'vectorized': True, 'random_state': 0}
        res1 = stats.permutation_test((x, y), statistic, batch=1, **kwds)
        assert_equal(statistic.counter, 1001)
        assert_equal(statistic.batch_size, 1)

        statistic.counter = 0
        res2 = stats.permutation_test((x, y), statistic, batch=50, **kwds)
        assert_equal(statistic.counter, 21)
        assert_equal(statistic.batch_size, 50)

        statistic.counter = 0
        res3 = stats.permutation_test((x, y), statistic, batch=1000, **kwds)
        assert_equal(statistic.counter, 2)
        assert_equal(statistic.batch_size, 1000)

        assert_equal(res1.pvalue, res3.pvalue)
        assert_equal(res2.pvalue, res3.pvalue)

    @pytest.mark.parametrize('permutation_type, exact_size',
                             [('pairings', special.factorial(3)**2),
                              ('samples', 2**3),
                              ('independent', special.binom(6, 3))])
    def test_permutations(self, permutation_type, exact_size):
        # make sure that the `permutations` parameter is respected by checking
        # the size of the null distribution
        np.random.seed(0)
        x = np.random.rand(3)
        y = np.random.rand(3)

        def statistic(x, y, axis):
            return np.mean(x, axis=axis) - np.mean(y, axis=axis)

        kwds = {'permutation_type': permutation_type,
                'vectorized': True, 'random_state': 0}
        res = stats.permutation_test((x, y), statistic, n_resamples=3, **kwds)
        assert_equal(res.null_distribution.size, 3)

        res = stats.permutation_test((x, y), statistic, **kwds)
        assert_equal(res.null_distribution.size, exact_size)

    # -- Randomized Permutation Tests -- #

    # To get reasonable accuracy, these next three tests are somewhat slow.
    # Originally, I had them passing for all combinations of permutation type,
    # alternative, and RNG, but that takes too long for CI. Instead, split
    # into three tests, each testing a particular combination of the three
    # parameters.

    def test_randomized_test_against_exact_both(self):
        # check that the randomized and exact tests agree to reasonable
        # precision for permutation_type='both

        alternative, rng = 'less', 0

        nx, ny, permutations = 8, 9, 24000
        assert special.binom(nx + ny, nx) > permutations

        x = stats.norm.rvs(size=nx)
        y = stats.norm.rvs(size=ny)
        data = x, y

        def statistic(x, y, axis):
            return np.mean(x, axis=axis) - np.mean(y, axis=axis)

        kwds = {'vectorized': True, 'permutation_type': 'independent',
                'batch': 100, 'alternative': alternative, 'random_state': rng}
        res = permutation_test(data, statistic, n_resamples=permutations,
                               **kwds)
        res2 = permutation_test(data, statistic, n_resamples=np.inf, **kwds)

        assert res.statistic == res2.statistic
        assert_allclose(res.pvalue, res2.pvalue, atol=1e-2)

    @pytest.mark.slow()
    def test_randomized_test_against_exact_samples(self):
        # check that the randomized and exact tests agree to reasonable
        # precision for permutation_type='samples'

        alternative, rng = 'greater', None

        nx, ny, permutations = 15, 15, 32000
        assert 2**nx > permutations

        x = stats.norm.rvs(size=nx)
        y = stats.norm.rvs(size=ny)
        data = x, y

        def statistic(x, y, axis):
            return np.mean(x - y, axis=axis)

        kwds = {'vectorized': True, 'permutation_type': 'samples',
                'batch': 100, 'alternative': alternative, 'random_state': rng}
        res = permutation_test(data, statistic, n_resamples=permutations,
                               **kwds)
        res2 = permutation_test(data, statistic, n_resamples=np.inf, **kwds)

        assert res.statistic == res2.statistic
        assert_allclose(res.pvalue, res2.pvalue, atol=1e-2)

    def test_randomized_test_against_exact_pairings(self):
        # check that the randomized and exact tests agree to reasonable
        # precision for permutation_type='pairings'

        alternative = 'two-sided'
        try:
            rng = np.random.default_rng(1)
        except AttributeError:
            rng = np.random.RandomState(1)

        nx, ny, permutations = 8, 8, 40000
        assert special.factorial(nx) > permutations

        x = stats.norm.rvs(size=nx)
        y = stats.norm.rvs(size=ny)
        data = [x]

        def statistic1d(x):
            return stats.pearsonr(x, y)[0]

        statistic = _resampling._vectorize_statistic(statistic1d)

        kwds = {'vectorized': True, 'permutation_type': 'samples',
                'batch': 100, 'alternative': alternative, 'random_state': rng}
        res = permutation_test(data, statistic, n_resamples=permutations,
                               **kwds)
        res2 = permutation_test(data, statistic, n_resamples=np.inf, **kwds)

        assert res.statistic == res2.statistic
        assert_allclose(res.pvalue, res2.pvalue, atol=1e-2)

    @pytest.mark.parametrize('alternative', ('less', 'greater'))
    # Different conventions for two-sided p-value here VS ttest_ind.
    # Eventually, we can add multiple options for the two-sided alternative
    # here in permutation_test.
    @pytest.mark.parametrize('permutations', (30, 1e9))
    @pytest.mark.parametrize('axis', (0, 1, 2))
    def test_against_permutation_ttest(self, alternative, permutations, axis):
        # check that this function and ttest_ind with permutations give
        # essentially identical results.

        x = np.arange(3*4*5).reshape(3, 4, 5)
        y = np.moveaxis(np.arange(4)[:, None, None], 0, axis)

        res1 = stats.ttest_ind(x, y, permutations=permutations, axis=axis,
                               random_state=0, alternative=alternative)

        def statistic(x, y, axis):
            return stats.ttest_ind(x, y, axis=axis).statistic

        res2 = permutation_test((x, y), statistic, vectorized=True,
                                n_resamples=permutations,
                                alternative=alternative, axis=axis,
                                random_state=0)

        assert_allclose(res1.statistic, res2.statistic, rtol=self.rtol)

        if permutations == 30:
            # Even one-sided p-value is defined differently in ttest_ind for
            # randomized tests. See permutation_test references [2] and [3].
            assert_allclose((res1.pvalue*30+1)/31, res2.pvalue, rtol=self.rtol)
        else:
            assert_allclose(res1.pvalue, res2.pvalue, rtol=self.rtol)

    # -- Independent (Unpaired) Sample Tests -- #

    def test_against_kstest(self):
        np.random.seed(0)
        x = stats.norm.rvs(size=4, scale=1)
        y = stats.norm.rvs(size=5, loc=3, scale=3)

        alternative = 'greater'
        expected = stats.ks_2samp(x, y, alternative=alternative, mode='exact')

        def statistic1d(x, y):
            return stats.ks_2samp(x, y, mode='asymp',
                                  alternative=alternative).statistic

        res = permutation_test((x, y), statistic1d, n_resamples=np.inf,
                               alternative=alternative)

        assert_allclose(res.statistic, expected.statistic, rtol=self.rtol)
        assert_allclose(res.pvalue, expected.pvalue, rtol=self.rtol)

    @pytest.mark.parametrize('alternative', ("less", "greater", "two-sided"))
    def test_against_ansari(self, alternative):
        np.random.seed(0)
        x = stats.norm.rvs(size=4, scale=1)
        y = stats.norm.rvs(size=5, scale=3)

        # ansari has a different convention for 'alternative'
        alternative_correspondence = {"less": "greater",
                                      "greater": "less",
                                      "two-sided": "two-sided"}
        alternative_scipy = alternative_correspondence[alternative]
        expected = stats.ansari(x, y, alternative=alternative_scipy)

        def statistic1d(x, y):
            return stats.ansari(x, y).statistic

        res = permutation_test((x, y), statistic1d, n_resamples=np.inf,
                               alternative=alternative)

        assert_allclose(res.statistic, expected.statistic, rtol=self.rtol)
        assert_allclose(res.pvalue, expected.pvalue, rtol=self.rtol)

    @pytest.mark.parametrize('alternative', ("less", "greater", "two-sided"))
    def test_against_mannwhitneyu(self, alternative):
        np.random.seed(0)
        x = stats.uniform.rvs(size=(3, 5, 2), loc=0)
        y = stats.uniform.rvs(size=(3, 5, 2), loc=0.05)

        expected = stats.mannwhitneyu(x, y, axis=1, alternative=alternative)

        def statistic(x, y, axis):
            return stats.mannwhitneyu(x, y, axis=axis).statistic

        res = permutation_test((x, y), statistic, vectorized=True,
                               n_resamples=np.inf, alternative=alternative,
                               axis=1)

        assert_allclose(res.statistic, expected.statistic, rtol=self.rtol)
        assert_allclose(res.pvalue, expected.pvalue, rtol=self.rtol)

    def test_against_cvm(self):
        np.random.seed(0)
        x = stats.norm.rvs(size=4, scale=1)
        y = stats.norm.rvs(size=5, loc=3, scale=3)

        expected = stats.cramervonmises_2samp(x, y, method='exact')

        def statistic1d(x, y):
            return stats.cramervonmises_2samp(x, y,
                                              method='asymptotic').statistic

        # cramervonmises_2samp has only one alternative, greater
        res = permutation_test((x, y), statistic1d, n_resamples=np.inf,
                               alternative='greater')

        assert_allclose(res.statistic, expected.statistic, rtol=self.rtol)
        assert_allclose(res.pvalue, expected.pvalue, rtol=self.rtol)

    @pytest.mark.xslow()
    @pytest.mark.parametrize('axis', (-1, 2))
    def test_vectorized_nsamp_ptype_both(self, axis):
        # Test that permutation_test with permutation_type='independent' works
        # properly for a 3-sample statistic with nd array samples of different
        # (but compatible) shapes and ndims. Show that exact permutation test
        # and random permutation tests approximate SciPy's asymptotic pvalues
        # and that exact and random permutation test results are even closer
        # to one another (than they are to the asymptotic results).
        np.random.seed(0)

        # Three samples, different (but compatible) shapes with different ndims
        x = np.random.rand(3)
        y = np.random.rand(1, 3, 2)
        z = np.random.rand(2, 1, 4)
        data = (x, y, z)

        # Define the statistic (and pvalue for comparison)
        def statistic1d(*data):
            return stats.kruskal(*data).statistic

        def pvalue1d(*data):
            return stats.kruskal(*data).pvalue

        statistic = _resampling._vectorize_statistic(statistic1d)
        pvalue = _resampling._vectorize_statistic(pvalue1d)

        # Calculate the expected results
        x2 = np.broadcast_to(x, (2, 3, 3))  # broadcast manually because
        y2 = np.broadcast_to(y, (2, 3, 2))  # _vectorize_statistic doesn't
        z2 = np.broadcast_to(z, (2, 3, 4))
        expected_statistic = statistic(x2, y2, z2, axis=axis)
        expected_pvalue = pvalue(x2, y2, z2, axis=axis)

        # Calculate exact and randomized permutation results
        kwds = {'vectorized': False, 'axis': axis, 'alternative': 'greater',
                'permutation_type': 'independent', 'random_state': 0}
        res = permutation_test(data, statistic1d, n_resamples=np.inf, **kwds)
        res2 = permutation_test(data, statistic1d, n_resamples=1000, **kwds)

        # Check results
        assert_allclose(res.statistic, expected_statistic, rtol=self.rtol)
        assert_allclose(res.statistic, res2.statistic, rtol=self.rtol)
        assert_allclose(res.pvalue, expected_pvalue, atol=6e-2)
        assert_allclose(res.pvalue, res2.pvalue, atol=3e-2)

    # -- Paired-Sample Tests -- #

    @pytest.mark.parametrize('alternative', ("less", "greater", "two-sided"))
    def test_against_wilcoxon(self, alternative):
        np.random.seed(0)
        x = stats.uniform.rvs(size=(3, 6, 2), loc=0)
        y = stats.uniform.rvs(size=(3, 6, 2), loc=0.05)

        # We'll check both 1- and 2-sample versions of the same test;
        # we expect identical results to wilcoxon in all cases.
        def statistic_1samp_1d(z):
            # 'less' ensures we get the same of two statistics every time
            return stats.wilcoxon(z, alternative='less').statistic

        def statistic_2samp_1d(x, y):
            return stats.wilcoxon(x, y, alternative='less').statistic

        def test_1d(x, y):
            return stats.wilcoxon(x, y, alternative=alternative)

        test = _resampling._vectorize_statistic(test_1d)

        expected = test(x, y, axis=1)
        expected_stat = expected[0]
        expected_p = expected[1]

        res1 = permutation_test((x-y,), statistic_1samp_1d, vectorized=False,
                                permutation_type='samples', n_resamples=np.inf,
                                alternative=alternative, axis=1)

        res2 = permutation_test((x, y), statistic_2samp_1d, vectorized=False,
                                permutation_type='samples', n_resamples=np.inf,
                                alternative=alternative, axis=1)

        # `wilcoxon` returns a different statistic with 'two-sided'
        assert_allclose(res1.statistic, res2.statistic, rtol=self.rtol)
        if alternative != 'two-sided':
            assert_allclose(res2.statistic, expected_stat, rtol=self.rtol)

        assert_allclose(res2.pvalue, expected_p, rtol=self.rtol)
        assert_allclose(res1.pvalue, res2.pvalue, rtol=self.rtol)

    @pytest.mark.parametrize('alternative', ("less", "greater", "two-sided"))
    def test_against_binomtest(self, alternative):
        np.random.seed(0)
        x = np.random.randint(0, 2, size=10)
        x[x == 0] = -1
        # More naturally, the test would flip elements between 0 and one.
        # However, permutation_test will flip the _signs_ of the elements.
        # So we have to work with +1/-1 instead of 1/0.

        def statistic(x, axis=0):
            return np.sum(x > 0, axis=axis)

        k, n, p = statistic(x), 10, 0.5
        expected = stats.binomtest(k, n, p, alternative=alternative)

        res = stats.permutation_test((x,), statistic, vectorized=True,
                                     permutation_type='samples',
                                     n_resamples=np.inf,
                                     alternative=alternative)
        assert_allclose(res.pvalue, expected.pvalue, rtol=self.rtol)

    # -- Exact Association Tests -- #

    def test_against_kendalltau(self):
        np.random.seed(0)
        x = stats.norm.rvs(size=6)
        y = x + stats.norm.rvs(size=6)

        expected = stats.kendalltau(x, y, method='exact')

        def statistic1d(x):
            return stats.kendalltau(x, y, method='asymptotic').correlation

        # kendalltau currently has only one alternative, two-sided
        res = permutation_test((x,), statistic1d, permutation_type='pairings',
                               n_resamples=np.inf)

        assert_allclose(res.statistic, expected.correlation, rtol=self.rtol)
        assert_allclose(res.pvalue, expected.pvalue, rtol=self.rtol)

    @pytest.mark.parametrize('alternative', ('less', 'greater', 'two-sided'))
    def test_against_fisher_exact(self, alternative):

        def statistic(x,):
            return np.sum((x == 1) & (y == 1))

        np.random.seed(0)
        # x and y are binary random variables with some dependence
        x = (np.random.rand(7) > 0.6).astype(float)
        y = (np.random.rand(7) + 0.25*x > 0.6).astype(float)
        tab = stats.contingency.crosstab(x, y)[1]

        res = permutation_test((x,), statistic, permutation_type='pairings',
                               n_resamples=np.inf, alternative=alternative)
        res2 = stats.fisher_exact(tab, alternative=alternative)

        assert_allclose(res.pvalue, res2[1])

    @pytest.mark.xslow()
    @pytest.mark.parametrize('axis', (-2, 1))
    def test_vectorized_nsamp_ptype_samples(self, axis):
        # Test that permutation_test with permutation_type='samples' works
        # properly for a 3-sample statistic with nd array samples of different
        # (but compatible) shapes and ndims. Show that exact permutation test
        # reproduces SciPy's exact pvalue and that random permutation test
        # approximates it.

        np.random.seed(0)

        x = np.random.rand(2, 4, 3)
        y = np.random.rand(1, 4, 3)
        z = np.random.rand(2, 4, 1)
        x = stats.rankdata(x, axis=axis)
        y = stats.rankdata(y, axis=axis)
        z = stats.rankdata(z, axis=axis)
        y = y[0]  # to check broadcast with different ndim
        data = (x, y, z)

        def statistic1d(*data):
            return stats.page_trend_test(data, ranked=True,
                                         method='asymptotic').statistic

        def pvalue1d(*data):
            return stats.page_trend_test(data, ranked=True,
                                         method='exact').pvalue

        statistic = _resampling._vectorize_statistic(statistic1d)
        pvalue = _resampling._vectorize_statistic(pvalue1d)

        expected_statistic = statistic(*np.broadcast_arrays(*data), axis=axis)
        expected_pvalue = pvalue(*np.broadcast_arrays(*data), axis=axis)

        kwds = {'vectorized': False, 'axis': axis, 'alternative': 'greater',
                'permutation_type': 'pairings', 'random_state': 0}
        res = permutation_test(data, statistic1d, n_resamples=np.inf, **kwds)
        res2 = permutation_test(data, statistic1d, n_resamples=5000, **kwds)

        assert_allclose(res.statistic, expected_statistic, rtol=self.rtol)
        assert_allclose(res.statistic, res2.statistic, rtol=self.rtol)
        assert_allclose(res.pvalue, expected_pvalue, rtol=self.rtol)
        assert_allclose(res.pvalue, res2.pvalue, atol=3e-2)

    # -- Test Against External References -- #

    tie_case_1 = {'x': [1, 2, 3, 4], 'y': [1.5, 2, 2.5],
                  'expected_less': 0.2000000000,
                  'expected_2sided': 0.4,  # 2*expected_less
                  'expected_Pr_gte_S_mean': 0.3428571429,  # see note below
                  'expected_statistic': 7.5,
                  'expected_avg': 9.142857, 'expected_std': 1.40698}
    tie_case_2 = {'x': [111, 107, 100, 99, 102, 106, 109, 108],
                  'y': [107, 108, 106, 98, 105, 103, 110, 105, 104],
                  'expected_less': 0.1555738379,
                  'expected_2sided': 0.3111476758,
                  'expected_Pr_gte_S_mean': 0.2969971205,  # see note below
                  'expected_statistic': 32.5,
                  'expected_avg': 38.117647, 'expected_std': 5.172124}

    @pytest.mark.xslow()  # only the second case is slow, really
    @pytest.mark.parametrize('case', (tie_case_1, tie_case_2))
    def test_with_ties(self, case):
        """
        Results above from SAS PROC NPAR1WAY, e.g.

        DATA myData;
        INPUT X Y;
        CARDS;
        1 1
        1 2
        1 3
        1 4
        2 1.5
        2 2
        2 2.5
        ods graphics on;
        proc npar1way AB data=myData;
            class X;
            EXACT;
        run;
        ods graphics off;

        Note: SAS provides Pr >= |S-Mean|, which is different from our
        definition of a two-sided p-value.

        """

        x = case['x']
        y = case['y']

        expected_statistic = case['expected_statistic']
        expected_less = case['expected_less']
        expected_2sided = case['expected_2sided']
        expected_Pr_gte_S_mean = case['expected_Pr_gte_S_mean']
        expected_avg = case['expected_avg']
        expected_std = case['expected_std']

        def statistic1d(x, y):
            return stats.ansari(x, y).statistic

        with np.testing.suppress_warnings() as sup:
            sup.filter(UserWarning, "Ties preclude use of exact statistic")
            res = permutation_test((x, y), statistic1d, n_resamples=np.inf,
                                   alternative='less')
            res2 = permutation_test((x, y), statistic1d, n_resamples=np.inf,
                                    alternative='two-sided')

        assert_allclose(res.statistic, expected_statistic, rtol=self.rtol)
        assert_allclose(res.pvalue, expected_less, atol=1e-10)
        assert_allclose(res2.pvalue, expected_2sided, atol=1e-10)
        assert_allclose(res2.null_distribution.mean(), expected_avg, rtol=1e-6)
        assert_allclose(res2.null_distribution.std(), expected_std, rtol=1e-6)

        # SAS provides Pr >= |S-Mean|; might as well check against that, too
        S = res.statistic
        mean = res.null_distribution.mean()
        n = len(res.null_distribution)
        Pr_gte_S_mean = np.sum(np.abs(res.null_distribution-mean)
                               >= np.abs(S-mean))/n
        assert_allclose(expected_Pr_gte_S_mean, Pr_gte_S_mean)

    @pytest.mark.parametrize('alternative, expected_pvalue',
                             (('less', 0.9708333333333),
                              ('greater', 0.05138888888889),
                              ('two-sided', 0.1027777777778)))
    def test_against_spearmanr_in_R(self, alternative, expected_pvalue):
        """
        Results above from R cor.test, e.g.

        options(digits=16)
        x <- c(1.76405235, 0.40015721, 0.97873798,
               2.2408932, 1.86755799, -0.97727788)
        y <- c(2.71414076, 0.2488, 0.87551913,
               2.6514917, 2.01160156, 0.47699563)
        cor.test(x, y, method = "spearm", alternative = "t")
        """
        np.random.seed(0)
        x = stats.norm.rvs(size=6)
        y = x + stats.norm.rvs(size=6)

        expected_statistic = 0.7714285714285715

        def statistic1d(x):
            return stats.spearmanr(x, y).correlation

        res = permutation_test((x,), statistic1d, permutation_type='pairings',
                               n_resamples=np.inf, alternative=alternative)

        assert_allclose(res.statistic, expected_statistic, rtol=self.rtol)
        assert_allclose(res.pvalue, expected_pvalue, atol=1e-13)

    @pytest.mark.parametrize("batch", (-1, 0))
    def test_batch_generator_iv(self, batch):
        with pytest.raises(ValueError, match="`batch` must be positive."):
            list(_resampling._batch_generator([1, 2, 3], batch))

    batch_generator_cases = [(range(0), 3, []),
                             (range(6), 3, [[0, 1, 2], [3, 4, 5]]),
                             (range(8), 3, [[0, 1, 2], [3, 4, 5], [6, 7]])]

    @pytest.mark.parametrize("iterable, batch, expected",
                             batch_generator_cases)
    def test_batch_generator(self, iterable, batch, expected):
        got = list(_resampling._batch_generator(iterable, batch))
        assert got == expected


def test_all_partitions_concatenated():
    # make sure that _all_paritions_concatenated produces the correct number
    # of partitions of the data into samples of the given sizes and that
    # all are unique
    n = np.array([3, 2, 4], dtype=int)
    nc = np.cumsum(n)

    all_partitions = set()
    counter = 0
    for partition_concatenated in _resampling._all_partitions_concatenated(n):
        counter += 1
        partitioning = np.split(partition_concatenated, nc[:-1])
        all_partitions.add(tuple([frozenset(i) for i in partitioning]))

    expected = np.product([special.binom(sum(n[i:]), sum(n[i+1:]))
                           for i in range(len(n)-1)])

    assert_equal(counter, expected)
    assert_equal(len(all_partitions), expected)