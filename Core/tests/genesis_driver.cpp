// Headless conformance driver, not a persistent service or production CLI.
#include "genesis.hpp"
#include "binary_stdio.hpp"
#include "wire.hpp"
#include <iostream>

int main(int argc,char** argv) {
    fantasy_world_generator::use_binary_stdio();
    using namespace fantasy_world_generator;
    try {
        if(argc!=2) throw Error("INVALID_INPUT");
        std::string bytes;char c;
        while(std::cin.get(c)) {
            if(bytes.size()==json::max_bytes) throw Error("INVALID_INPUT");
            bytes+=c;
        }
        const std::string op=argv[1];
        auto value=json::parse(bytes);
        if(op=="unreal_cm") std::cout<<unreal_point_json(unreal_point(value));
        else if(op=="validate_generate") std::cout<<generate_request_json(generate_request(value));
        else throw Error("INVALID_INPUT");
        return 0;
    } catch(const Error& error) {std::cout<<failure_json(error);return 2;}
    catch(const std::exception& error) {std::cerr<<error.what();return 3;}
}
