#pragma once
// TEST ADAPTER for the three small string utilities called by hybrid.cpp.
#include <string>
#include <vector>
namespace qbrain::util {
inline std::string replace_all(std::string s,const std::string&a,const std::string&b){
  size_t p=0;while(!a.empty()&&(p=s.find(a,p))!=std::string::npos){s.replace(p,a.size(),b);p+=b.size();}return s;
}
inline std::string to_lower(std::string s){for(char&c:s)if(c>='A'&&c<='Z')c=static_cast<char>(c-'A'+'a');return s;}
inline std::vector<std::string> split(const std::string&s,char d){
  std::vector<std::string> out;size_t p=0;while(true){auto q=s.find(d,p);out.push_back(s.substr(p,q-p));if(q==std::string::npos)break;p=q+1;}return out;
}
}
