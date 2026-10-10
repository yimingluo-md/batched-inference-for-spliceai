// Streaming descriptive audit of released SpliceAI SNV VCFs (no inference).
#include <zlib.h>
#include <algorithm>
#include <array>
#include <charconv>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
using U = uint64_t;
using S = std::string_view;
template <class T> void arr(std::ostream& o, const T& a) {
    o << '['; bool first = true;
    for (auto v : a) { if (!first) o << ','; first = false; o << v; } o << ']';
}
std::vector<S> split(S s, char delim) {
    std::vector<S> out; size_t start=0, end;
    while ((end=s.find(delim,start)) != S::npos) { out.push_back(s.substr(start,end-start)); start=end+1; }
    out.push_back(s.substr(start)); return out;
}
int integer(S s) {
    int v; auto r=std::from_chars(s.data(),s.data()+s.size(),v);
    if(r.ec!=std::errc() || r.ptr!=s.data()+s.size()) throw std::runtime_error("invalid integer");
    return v;
}
int score(S s) {
    if(s=="-0.00") return 0;
    if(s.size()!=4 || s[1]!='.' || s[0]<'0' || s[0]>'1' || s[2]<'0' || s[2]>'9' || s[3]<'0' || s[3]>'9')
        throw std::runtime_error("score not two-decimal numeric");
    int v=(s[0]-'0')*100+(s[2]-'0')*10+s[3]-'0';
    if(v>100) throw std::runtime_error("score outside [0,1]");
    return v;
}
int main(int argc,char** argv) {
  U n=0;
  try {
    if(argc!=4) throw std::runtime_error("usage: score_audit INPUT.vcf.gz CONTIG OUTPUT.json");
    gzFile f=gzopen(argv[1],"rb"); if(!f) throw std::runtime_error("open failed");
    gzbuffer(f,1<<20);
    std::vector<char> buf(131072);
    U entries=0, multi=0, signed_zero=0;
    std::array<U,101> vh{}, eh{};
    std::array<std::array<U,101>,4> event_hist{}, distal_event_hist{};
    const std::array<int,4> thresholds={1,20,50,80};
    std::array<U,4> variant_distal{}, entry_distal{};
    std::map<size_t,U> multiplicity;
    std::map<std::string,U> genes;
    int previous_pos=0; char previous_alt=0;
    while(gzgets(f,buf.data(),buf.size())) {
      S line(buf.data()); if(line.empty() || line.back()!='\n') throw std::runtime_error("unterminated or oversized line");
      line.remove_suffix(1); if(!line.empty() && line.back()=='\r') line.remove_suffix(1);
      if(line.empty()) throw std::runtime_error("empty VCF line");
      if(line[0]=='#') continue;
      auto cols=split(line,'\t');
      if(cols.size()!=8 || cols[0]!=argv[2]) throw std::runtime_error("invalid columns or contig");
      int pos=integer(cols[1]);
      if(cols[3].size()!=1 || cols[4].size()!=1 || S("ACGT").find(cols[3])==S::npos || S("ACGT").find(cols[4])==S::npos || cols[3]==cols[4]) throw std::runtime_error("not a nonreference ACGT SNV");
      if(pos<previous_pos || (pos==previous_pos && cols[4][0]<=previous_alt)) throw std::runtime_error("unsorted or duplicate variant");
      previous_pos=pos; previous_alt=cols[4][0];
      S annot; int matches=0;
      for(S item:split(cols[7],';')) if(item.substr(0,9)=="SpliceAI=") { annot=item.substr(9); ++matches; }
      if(matches!=1 || annot.empty()) throw std::runtime_error("missing/duplicate SpliceAI field");
      auto annotations=split(annot,',');
      std::vector<S> seen; int vmax=0; std::array<bool,4> vd{};
      for(S a:annotations) {
        auto fields=split(a,'|');
        if(fields.size()!=10 || fields[0]!=cols[4] || fields[1].empty()) throw std::runtime_error("invalid annotation");
        if(std::find(seen.begin(),seen.end(),fields[1])!=seen.end()) throw std::runtime_error("duplicate gene annotation");
        seen.push_back(fields[1]); ++genes[std::string(fields[1])];
        int emax=0; std::array<bool,4> ed{};
        for(int j=0;j<4;++j) {
          signed_zero+=(fields[2+j]=="-0.00");
          int ds=score(fields[2+j]), dp=integer(fields[6+j]);
          if(dp < -500 || dp>500) throw std::runtime_error("position outside D500");
          ++event_hist[j][ds]; emax=std::max(emax,ds);
          if(ds>0 && (dp < -50 || dp>50)) {
            ++distal_event_hist[j][ds];
            for(int t=0;t<4;++t) if(ds>=thresholds[t]) ed[t]=vd[t]=true;
          }
        }
        ++eh[emax]; vmax=std::max(vmax,emax); ++entries;
        for(int t=0;t<4;++t) entry_distal[t]+=ed[t];
      }
      ++n; ++vh[vmax]; ++multiplicity[seen.size()]; multi+=(seen.size()>1);
      for(int t=0;t<4;++t) variant_distal[t]+=vd[t];
    }
    int zcode; gzerror(f,&zcode); if(zcode!=Z_OK && zcode!=Z_STREAM_END) throw std::runtime_error("gzip read error");
    if(gzclose(f)!=Z_OK || !n) throw std::runtime_error("gzip close error or empty file");
    std::ofstream o(argv[3]); if(!o) throw std::runtime_error("output open failed");
    o << "{\n\"schema_version\":1,\n\"contig\":\"" << argv[2] << "\",\n\"records\":" << n << ",\n\"variant_gene_entries\":" << entries << ",\n\"multigene_records\":" << multi << ",\n\"unique_genes\":" << genes.size() << ",\n\"variant_max_histogram\":";
    arr(o,vh); o << ",\n\"signed_zero_score_fields\":" << signed_zero;
    o << ",\n\"entry_max_histogram\":"; arr(o,eh);
    o << ",\n\"distal_score_thresholds_hundredths\":"; arr(o,thresholds);
    o << ",\n\"variants_with_distal_event\":"; arr(o,variant_distal);
    o << ",\n\"entries_with_distal_event\":"; arr(o,entry_distal);
    const char* names[]={"AG","AL","DG","DL"};
    for(int j=0;j<4;++j) { o << ",\n\"" << names[j] << "_histogram\":"; arr(o,event_hist[j]); o << ",\n\"" << names[j] << "_distal_histogram\":"; arr(o,distal_event_hist[j]); }
    o << ",\n\"gene_multiplicity\":{"; bool first=true;
    for(auto p:multiplicity) { if(!first)o<<','; first=false; o << '"' << p.first << "\":" << p.second; }
    o << "},\n\"gene_entry_counts\":{"; first=true;
    for(auto p:genes) { if(p.first.find_first_of("\\\"\n\r")!=std::string::npos)throw std::runtime_error("unsafe gene name"); if(!first)o<<',';first=false;o<<'"'<<p.first<<"\":"<<p.second; }
    o << "}\n}\n"; o.close(); if(!o)throw std::runtime_error("write failed");
    std::cerr << "records="<<n<<" entries="<<entries<<"\n";
  } catch(const std::exception& e) { std::cerr<<"FAILED after "<<n<<" records: "<<e.what()<<"\n"; return 1; }
}
