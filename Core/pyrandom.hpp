#pragma once
#include <cstdint>
#include <string>
#include <vector>
namespace fantasy_world_generator {
// Mersenne Twister stream of the reference generator. Plate layout draws from this
// sequence, so the native world only replays a Python seed while the stream matches.
class PyRandom {
public:
    explicit PyRandom(std::uint64_t seed);
    double next();                                   // random(): 53 bits in [0,1)
    double uniform(double low,double high);
    double gauss(double mu,double sigma);
    // getrandbits and the rejection loop under randrange/choice, so a ported
    // selection consumes the same words the reference does.
    std::uint64_t getrandbits(int bits);
    std::uint64_t randbelow(std::uint64_t bound);
    std::int64_t randrange(std::int64_t start,std::int64_t stop);
    std::int64_t randint(std::int64_t low,std::int64_t high);
    std::size_t choice(std::size_t count);
    // random.choices with weights: cumulative bisect on one uniform draw.
    std::size_t weighted_choice(const std::vector<double>& weights);
    // random.sample(range(n), k) as indices, in draw order.
    //
    // CPython picks between two algorithms on the population size, and the two
    // consume completely different word sequences, so the choice is part of the
    // stream and not an optimisation we may make differently. Both branches occur
    // in this generator: a large city takes the selection-set branch, a small or
    // heavily clipped site takes the pool branch.
    std::vector<std::size_t> sample_indices(std::size_t n,std::size_t k);
private:
    std::uint32_t word();
    std::vector<std::uint32_t> state_;
    std::size_t index_=0;
    bool spare_ready_=false;
    double spare_=0.;
};
// sha256('tectonics-v1:master:domain:variation')[:4] as a big-endian uint32.
std::uint32_t child_seed(std::uint64_t master,const std::string& domain,std::uint64_t variation=0);
std::uint32_t child_seed_text(const std::string& master,const std::string& domain,std::uint64_t variation=0);
}
