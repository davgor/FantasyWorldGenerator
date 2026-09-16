// Headless conformance driver, not a persistent service or production CLI.
#include "wire.hpp"
#include "numeric.hpp"
#include <iomanip>
#include <iostream>
#include <locale>

int main(int argc,char** argv) {
    using namespace mathlab;
    try {
        if(argc!=2) throw Error("INVALID_INPUT");
        std::string bytes;char c;
        while(std::cin.get(c)) {
            if(bytes.size()==json::max_bytes) throw Error("INVALID_INPUT");
            bytes+=c;
        }
        const std::string op=argv[1];
        if(op=="sha256") {std::cout<<sha256(bytes);return 0;}
        auto value=json::parse(bytes);
        if(op=="canonical") std::cout<<json::canonical(value);
        else if(op=="digest") std::cout<<digest(value);
        else if(op=="stream") {
            std::int64_t version=1;
            if(json::object(value).count("version")) {
                json::exact(value,{"seed","stream","index","version"});version=json::integer(json::field(value,"version"));
            } else json::exact(value,{"seed","stream","index"});
            std::cout<<random_word(json::string(json::field(value,"seed")),json::string(json::field(value,"stream")),json::integer(json::field(value,"index")),version);
        } else if(op=="unit") {std::cout.imbue(std::locale::classic());std::cout<<std::setprecision(17)<<unit_float(json::string(value));}
        else if(op=="snapshot") std::cout<<snapshot_json(snapshot_value(value));
        else if(op=="candidate") std::cout<<candidate_json(candidate_value(value));
        else if(op=="event") {event_value(value,"world:demo");std::cout<<json::canonical(value);}
        else if(op=="evaluate") {
            json::exact(value,{"state","command"});
            std::cout<<candidate_json(evaluate(snapshot_value(json::field(value,"state")),command_value(json::field(value,"command"))));
        } else if(op=="commit") {
            json::exact(value,{"state","candidate"});
            std::cout<<snapshot_json(commit(snapshot_value(json::field(value,"state")),candidate_value(json::field(value,"candidate"))));
        } else throw Error("INVALID_INPUT");
        return 0;
    } catch(const Error& error) {std::cout<<failure_json(error);return 2;}
    catch(const std::exception& error) {std::cerr<<error.what();return 3;}
}
