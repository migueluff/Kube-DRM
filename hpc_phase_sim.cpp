// simple_hpc_phases.cpp
// Minimal HPC phase emulator: memory grow/shrink (commit RSS), CPU burn, sleep.
// No access patterns, no complex partitioning. Thread-safe metrics.
//
// Build: g++ -O2 -std=c++17 -pthread hpc_phase_sim.cpp -o hpc_phase_sim

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

using namespace std;
using clk = std::chrono::steady_clock;

static std::atomic<bool> g_stop{false};
static void on_sigint(int){ g_stop.store(true); }

// ---------- utils ----------
static uint64_t parse_size_bytes(const std::string& s){
    if (s.empty()) return 0;
    size_t i=0;
    bool neg = (s[0]=='-'); bool pos = (s[0]=='+');
    if (neg||pos) i=1;
    while (i<s.size() && (isdigit(s[i])||s[i]=='.')) ++i;
    if (i==(size_t)(neg||pos)) throw runtime_error("Invalid size: "+s);
    double v = stod(s.substr(neg||pos, i-(neg||pos)));
    string u; if (i<s.size()) { u=s.substr(i); for (auto& c:u) c=toupper(c); }
    double mult = 1.0;
    if (u=="K"||u=="KB") mult = 1024.0;
    else if (u=="M"||u=="MB") mult = 1024.0*1024.0;
    else if (u=="G"||u=="GB") mult = 1024.0*1024.0*1024.0;
    else if (u=="T"||u=="TB") mult = 1024.0*1024.0*1024.0*1024.0;
    else if (u==""||u=="B") mult = 1.0;
    else throw runtime_error("Unknown size unit in: "+s);
    uint64_t bytes = static_cast<uint64_t>(v * mult);
    return neg ? (uint64_t)(- (int64_t)bytes) : bytes;
}

static double parse_duration_seconds(const std::string& s){
    if (s.empty()) return 0.0;
    size_t i=0; while (i<s.size() && (isdigit(s[i])||s[i]=='.')) ++i;
    if (i==0) throw runtime_error("Invalid duration: "+s);
    double v = stod(s.substr(0,i));
    string u = s.substr(i); for (auto& c:u) c=tolower(c);
    if (u=="" || u=="s") return v;
    if (u=="ms") return v/1000.0;
    if (u=="m") return v*60.0;
    if (u=="h") return v*3600.0;
    throw runtime_error("Unknown duration unit in: "+s);
}

static uint64_t read_vm_rss_kib(){
    ifstream f("/proc/self/status");
    string line;
    while (getline(f,line)) {
        if (line.rfind("VmRSS:",0)==0) {
            istringstream iss(line.substr(6));
            uint64_t kb=0; string kb_s; iss>>kb>>kb_s; return kb;
        }
    }
    return 0;
}

// ---------- global memory pool ----------
struct Buffer { unique_ptr<uint8_t[]> data; size_t size=0; };
struct MemState {
    vector<Buffer> bufs;
    size_t total=0;
    mutex mtx;
} g_mem;

static void commit_pages(uint8_t* p, size_t n){
    // Touch one byte per page to commit RSS
    if (!p || n==0) return;
    const size_t stride = 4096;
    volatile uint8_t sink=0;
    for (size_t i=0; i<n; i+=stride) { p[i]++; sink ^= p[i]; }
    (void)sink;
}

static void alloc_add(size_t bytes, size_t chunk = (size_t)256<<20 /*256MiB*/) {
    lock_guard<mutex> lk(g_mem.mtx);
    size_t remain = bytes;
    while (remain>0) {
        size_t this_chunk = std::min(remain, chunk);
        Buffer b;
        b.data = unique_ptr<uint8_t[]>(new (nothrow) uint8_t[this_chunk]);
        if (!b.data) throw bad_alloc();
        b.size = this_chunk;
        commit_pages(b.data.get(), b.size);
        g_mem.total += b.size;
        g_mem.bufs.push_back(std::move(b));
        remain -= this_chunk;
    }
}

static void free_bytes(size_t bytes){
    lock_guard<mutex> lk(g_mem.mtx);
    size_t remain = bytes;
    while (remain>0 && !g_mem.bufs.empty()){
        Buffer& back = g_mem.bufs.back();
        if (back.size <= remain) {
            remain -= back.size;
            g_mem.total -= back.size;
            g_mem.bufs.pop_back();
        } else {
            size_t keep = back.size - remain;
            unique_ptr<uint8_t[]> smaller(new (nothrow) uint8_t[keep]);
            if (!smaller) throw bad_alloc();
            memcpy(smaller.get(), back.data.get(), keep);
            back.data.swap(smaller);
            back.size = keep;
            g_mem.total -= remain;
            remain = 0;
        }
    }
}

// ---------- phases ----------
struct Phase {
    enum Type { MEM, CPU, SLEEP } type;
    // common
    double duration_s = 0.0; // only used for CPU/SLEEP (MEM applies instantly)
    // mem
    int64_t mem_abs = -1;     // >=0 => set absolute size
    int64_t mem_delta = 0;    // !=0 => add/remove
    // cpu
    int cpu_threads = 1;
    double cpu_util = 1.0;    // 0..1
};

static void run_cpu(double duration_s, int threads, double util){
    if (threads <= 0) threads = 1;
    if (util < 0.0) util = 0.0; if (util > 1.0) util = 1.0;

    atomic<bool> running{true};
    vector<thread> ts; ts.reserve(threads);

    auto worker = [&running, util](){
        const auto period = chrono::milliseconds(10);
        const auto busy_ns = chrono::nanoseconds( (long long)(util * 1e7) );
        volatile double x = 1.0;
        while (running.load(memory_order_relaxed) && !g_stop.load()){
            auto start = clk::now();
            while (chrono::duration_cast<chrono::nanoseconds>(clk::now() - start) < busy_ns) {
                // some flops
                x = x * 1.000001 + 0.999999;
            }
            auto elapsed = clk::now() - start;
            auto sleep_left = period - chrono::duration_cast<chrono::nanoseconds>(elapsed);
            if (sleep_left > chrono::nanoseconds(0)) this_thread::sleep_for(sleep_left);
        }
        (void)x;
    };

    for (int i=0;i<threads;++i) ts.emplace_back(worker);
    auto stop_at = clk::now() + chrono::duration<double>(duration_s);
    while (clk::now() < stop_at && !g_stop.load()) this_thread::sleep_for(chrono::milliseconds(50));
    running.store(false);
    for (auto& t: ts) t.join();
}

static void run_sleep(double duration_s) {
    using namespace std::chrono;
    if (duration_s <= 0.0) return;

    auto remaining = duration_s;
    while (remaining > 0.0 && !g_stop.load()) {
        double chunk = std::min(remaining, 1.0); // sleep in ≤1s chunks so Ctrl+C is responsive
        std::this_thread::sleep_for(duration<double>(chunk));
        remaining -= chunk;
    }
}

// ---------- CLI ----------
static void print_help(){
    cerr <<
R"(simple_hpc_phases — minimal CPU/MEM/SLEEP phase emulator

Usage:
  simple_hpc_phases [--log-interval=1s] [--name=JOB] --phase <spec> [--phase <spec>...]
  simple_hpc_phases --help

Phase specs:
  --phase type=mem,abs=<SIZE>|delta=<+/-SIZE>
  --phase type=cpu,threads=<N>,util=<0..1>,duration=<TIME>
  --phase type=sleep,duration=<TIME>

Notes:
  - Memory 'mem' phases apply immediately (allocation or free) and persist.
  - Sizes accept K,M,G,T (binary). TIME accepts ms,s,m,h.
Metrics:
  Prints: [metrics] name=... elapsed_s=... alloc_bytes=... VmRSS_kib=...
Examples:
  # Start at 2 GiB, compute 60s, spike +4 GiB, sleep, free 5 GiB
  --phase type=mem,abs=2G
  --phase type=cpu,threads=4,util=0.4,duration=60s
  --phase type=mem,delta=+4G
  --phase type=sleep,duration=10s
  --phase type=mem,delta=-5G
)";
}

static vector<pair<string,string>> split_kv(const string& s){
    vector<pair<string,string>> out;
    string cur; size_t i=0;
    auto flush=[&](){
        if (cur.empty()) return;
        auto eq = cur.find('=');
        if (eq==string::npos) throw runtime_error("Expected key=value in: "+cur);
        out.emplace_back(cur.substr(0,eq), cur.substr(eq+1));
        cur.clear();
    };
    for (; i<=s.size(); ++i){
        char c = (i<s.size()? s[i] : ',');
        if (c==',') flush(); else cur.push_back(c);
    }
    return out;
}

int main(int argc, char** argv){
    signal(SIGINT, on_sigint);
    signal(SIGTERM, on_sigint);

    vector<Phase> phases;
    double log_interval_s = 1.0;
    string job_name = "job";

    for (int i=1;i<argc;++i){
        string arg = argv[i];
        if (arg=="--help"||arg=="-h"){ print_help(); return 0; }
        else if (arg.rfind("--log-interval=",0)==0){
            log_interval_s = parse_duration_seconds(arg.substr(16));
        } else if (arg.rfind("--name=",0)==0){
            job_name = arg.substr(7);
        } else if (arg=="--phase"){
            if (i+1>=argc){ cerr<<"Missing spec after --phase\n"; return 1; }
            string spec = argv[++i];
            Phase p{};
            string type;
            for (auto& kv : split_kv(spec)) {
                string k=kv.first, v=kv.second;
                for (auto& c:k) c=tolower(c);
                if (k=="type") { type=v; for (auto& c:type) c=tolower(c); }
            }
            if (type=="mem") p.type=Phase::MEM;
            else if (type=="cpu") p.type=Phase::CPU;
            else if (type=="sleep") p.type=Phase::SLEEP;
            else { cerr<<"Unknown phase type in: "<<spec<<"\n"; return 1; }

            for (auto& kv : split_kv(spec)){
                string k=kv.first, v=kv.second; for (auto& c:k) c=tolower(c);
                if (k=="duration") p.duration_s = parse_duration_seconds(v);
                if (p.type==Phase::MEM){
                    if (k=="abs")   p.mem_abs   = (int64_t)parse_size_bytes(v);
                    if (k=="delta") p.mem_delta = (int64_t)parse_size_bytes(v);
                } else if (p.type==Phase::CPU){
                    if (k=="threads") p.cpu_threads = stoi(v);
                    if (k=="util")    p.cpu_util    = stod(v);
                }
            }
            phases.push_back(p);
        } else {
            cerr<<"Unknown arg: "<<arg<<"\n"; print_help(); return 1;
        }
    }

    if (phases.empty()){ print_help(); return 1; }

    auto t0 = clk::now();
    atomic<bool> logging{true};
    thread logger([&](){
        auto next = t0 + chrono::duration<double>(log_interval_s);
        while (logging.load() && !g_stop.load()){
            auto now = clk::now();
            if (now >= next) {
                double elapsed = chrono::duration<double>(now - t0).count();
                size_t alloc;
                { lock_guard<mutex> lk(g_mem.mtx); alloc = g_mem.total; }
                uint64_t rss_kib = read_vm_rss_kib();
                cerr << fixed << setprecision(1)
                     << "[metrics] name=" << job_name
                     << " elapsed_s=" << elapsed
                     << " alloc_bytes=" << alloc
                     << " VmRSS_kib=" << rss_kib
                     << "\n";
                next += chrono::duration<double>(log_interval_s);
            } else {
                this_thread::sleep_for(chrono::milliseconds(50));
            }
        }
    });

    size_t idx=0;
    for (auto& p : phases){
        if (g_stop.load()) break;
        cerr << "== Phase " << (++idx) << " ==\n";
        if (p.type==Phase::MEM){
            // Apply absolute first (if given), then delta.
            if (p.mem_abs >= 0){
                size_t target = (size_t)p.mem_abs;
                size_t cur; { lock_guard<mutex> lk(g_mem.mtx); cur = g_mem.total; }
                if (target > cur) alloc_add(target - cur);
                else if (target < cur) free_bytes(cur - target);
                cerr << "MEM: abs=" << target << " bytes\n";
            }
            if (p.mem_delta != 0){
                if (p.mem_delta > 0) { alloc_add((size_t)p.mem_delta); cerr << "MEM: +=" << (size_t)p.mem_delta << " bytes\n"; }
                else { free_bytes((size_t)(-p.mem_delta)); cerr << "MEM: -=" << (size_t)(-p.mem_delta) << " bytes\n"; }
            }
            if (p.duration_s > 0) run_sleep(p.duration_s); // optional hold time
        } else if (p.type==Phase::CPU){
            cerr << "CPU: threads="<<p.cpu_threads<<" util="<<p.cpu_util<<" duration="<<p.duration_s<<"s\n";
            run_cpu(p.duration_s, p.cpu_threads, p.cpu_util);
        } else {
            cerr << "SLEEP: duration="<<p.duration_s<<"s\n";
            run_sleep(p.duration_s);
        }
    }

    logging.store(false);
    logger.join();
    { lock_guard<mutex> lk(g_mem.mtx);
      cerr << "Done. Total allocated bytes=" << g_mem.total << "\n"; }
    return 0;
}
