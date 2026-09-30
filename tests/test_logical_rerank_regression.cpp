#include <exception>
#include <iostream>
void test_rerank();
#ifdef _WIN32
void test_n39_rerank_config();
#endif
int main(){try{test_rerank();
#ifdef _WIN32
test_n39_rerank_config();
std::cout<<"original rerank and N39 passed\n";
#else
std::cout<<"original rerank passed; Windows-only N39 not run here\n";
#endif
return 0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
