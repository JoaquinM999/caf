// MSVC compatibility stubs for Visual Studio 2022 STL vector algorithms
// when building on environments with Visual Studio 2019 MSVC runtimes.
#include <stddef.h>
#include <stdint.h>
#include <string.h>

struct PtrPair {
    const void* p1;
    const void* p2;
};

const void* __std_find_trivial_1(const void* first, const void* last, unsigned char val) {
    const unsigned char* f = (const unsigned char*)first;
    const unsigned char* l = (const unsigned char*)last;
    for (; f != l; ++f) {
        if (*f == val) return f;
    }
    return l;
}

const void* __std_find_trivial_2(const void* first, const void* last, unsigned short val) {
    const unsigned short* f = (const unsigned short*)first;
    const unsigned short* l = (const unsigned short*)last;
    for (; f != l; ++f) {
        if (*f == val) return f;
    }
    return l;
}

const void* __std_find_trivial_4(const void* first, const void* last, unsigned int val) {
    const unsigned int* f = (const unsigned int*)first;
    const unsigned int* l = (const unsigned int*)last;
    for (; f != l; ++f) {
        if (*f == val) return f;
    }
    return l;
}

const void* __std_find_trivial_8(const void* first, const void* last, unsigned long long val) {
    const unsigned long long* f = (const unsigned long long*)first;
    const unsigned long long* l = (const unsigned long long*)last;
    for (; f != l; ++f) {
        if (*f == val) return f;
    }
    return l;
}

const void* __std_find_last_trivial_1(const void* first, const void* last, unsigned char val) {
    const unsigned char* f = (const unsigned char*)first;
    const unsigned char* l = (const unsigned char*)last;
    while (l != f) {
        --l;
        if (*l == val) return l;
    }
    return (const unsigned char*)last;
}

const void* __std_find_last_trivial_2(const void* first, const void* last, unsigned short val) {
    const unsigned short* f = (const unsigned short*)first;
    const unsigned short* l = (const unsigned short*)last;
    while (l != f) {
        --l;
        if (*l == val) return l;
    }
    return (const unsigned short*)last;
}

void* __std_remove_1(void* first, void* last, unsigned char val) {
    unsigned char* f = (unsigned char*)first;
    unsigned char* l = (unsigned char*)last;
    unsigned char* out = f;
    for (; f != l; ++f) {
        if (*f != val) {
            *out++ = *f;
        }
    }
    return out;
}

void* __std_remove_2(void* first, void* last, unsigned short val) {
    unsigned short* f = (unsigned short*)first;
    unsigned short* l = (unsigned short*)last;
    unsigned short* out = f;
    for (; f != l; ++f) {
        if (*f != val) {
            *out++ = *f;
        }
    }
    return out;
}

void* __std_remove_8(void* first, void* last, unsigned long long val) {
    unsigned long long* f = (unsigned long long*)first;
    unsigned long long* l = (unsigned long long*)last;
    unsigned long long* out = f;
    for (; f != l; ++f) {
        if (*f != val) {
            *out++ = *f;
        }
    }
    return out;
}

size_t __std_count_trivial_4(const void* first, const void* last, unsigned int val) {
    const unsigned int* f = (const unsigned int*)first;
    const unsigned int* l = (const unsigned int*)last;
    size_t count = 0;
    for (; f != l; ++f) {
        if (*f == val) ++count;
    }
    return count;
}

size_t __std_count_trivial_8(const void* first, const void* last, unsigned long long val) {
    const unsigned long long* f = (const unsigned long long*)first;
    const unsigned long long* l = (const unsigned long long*)last;
    size_t count = 0;
    for (; f != l; ++f) {
        if (*f == val) ++count;
    }
    return count;
}

const void* __std_min_element_4(const int* first, const int* last) {
    if (first == last) return first;
    const int* best = first;
    for (++first; first != last; ++first) {
        if (*first < *best) best = first;
    }
    return best;
}

const void* __std_min_element_d(const double* first, const double* last) {
    if (first == last) return first;
    const double* best = first;
    for (++first; first != last; ++first) {
        if (*first < *best) best = first;
    }
    return best;
}

const void* __std_min_element_f(const float* first, const float* last) {
    if (first == last) return first;
    const float* best = first;
    for (++first; first != last; ++first) {
        if (*first < *best) best = first;
    }
    return best;
}

const void* __std_max_element_1(const unsigned char* first, const unsigned char* last) {
    if (first == last) return first;
    const unsigned char* best = first;
    for (++first; first != last; ++first) {
        if (*first > *best) best = first;
    }
    return best;
}

const void* __std_max_element_4(const int* first, const int* last) {
    if (first == last) return first;
    const int* best = first;
    for (++first; first != last; ++first) {
        if (*first > *best) best = first;
    }
    return best;
}

const void* __std_max_element_8(const long long* first, const long long* last) {
    if (first == last) return first;
    const long long* best = first;
    for (++first; first != last; ++first) {
        if (*first > *best) best = first;
    }
    return best;
}

const void* __std_max_element_d(const double* first, const double* last) {
    if (first == last) return first;
    const double* best = first;
    for (++first; first != last; ++first) {
        if (*first > *best) best = first;
    }
    return best;
}

const void* __std_max_element_f(const float* first, const float* last) {
    if (first == last) return first;
    const float* best = first;
    for (++first; first != last; ++first) {
        if (*first > *best) best = first;
    }
    return best;
}

const void* __std_max_4i(const int* first, const int* last) {
    return __std_max_element_4(first, last);
}

const void* __std_search_1(const unsigned char* first1, const unsigned char* last1, const unsigned char* first2, const unsigned char* last2) {
    size_t len2 = (size_t)(last2 - first2);
    if (len2 == 0) return first1;
    size_t len1 = (size_t)(last1 - first1);
    if (len1 < len2) return last1;
    for (; first1 + len2 <= last1; ++first1) {
        if (memcmp(first1, first2, len2) == 0) return first1;
    }
    return last1;
}

const void* __std_search_2(const unsigned short* first1, const unsigned short* last1, const unsigned short* first2, const unsigned short* last2) {
    size_t len2 = (size_t)(last2 - first2);
    if (len2 == 0) return first1;
    size_t len1 = (size_t)(last1 - first1);
    if (len1 < len2) return last1;
    for (; first1 + len2 <= last1; ++first1) {
        if (memcmp(first1, first2, len2 * sizeof(unsigned short)) == 0) return first1;
    }
    return last1;
}

const void* __std_find_end_1(const unsigned char* first1, const unsigned char* last1, const unsigned char* first2, const unsigned char* last2) {
    size_t len2 = (size_t)(last2 - first2);
    if (len2 == 0) return last1;
    size_t len1 = (size_t)(last1 - first1);
    if (len1 < len2) return last1;
    const unsigned char* res = last1;
    for (; first1 + len2 <= last1; ++first1) {
        if (memcmp(first1, first2, len2) == 0) res = first1;
    }
    return res;
}

const void* __std_find_end_2(const unsigned short* first1, const unsigned short* last1, const unsigned short* first2, const unsigned short* last2) {
    size_t len2 = (size_t)(last2 - first2);
    if (len2 == 0) return last1;
    size_t len1 = (size_t)(last1 - first1);
    if (len1 < len2) return last1;
    const unsigned short* res = last1;
    for (; first1 + len2 <= last1; ++first1) {
        if (memcmp(first1, first2, len2 * sizeof(unsigned short)) == 0) res = first1;
    }
    return res;
}

size_t __std_find_first_of_trivial_pos_1(const void* h, size_t h_size, const void* n, size_t n_size) {
    const unsigned char* hay = (const unsigned char*)h;
    const unsigned char* ndl = (const unsigned char*)n;
    for (size_t i = 0; i < h_size; ++i) {
        for (size_t j = 0; j < n_size; ++j) {
            if (hay[i] == ndl[j]) return i;
        }
    }
    return (size_t)-1;
}

size_t __std_find_first_of_trivial_pos_2(const void* h, size_t h_size, const void* n, size_t n_size) {
    const unsigned short* hay = (const unsigned short*)h;
    const unsigned short* ndl = (const unsigned short*)n;
    for (size_t i = 0; i < h_size; ++i) {
        for (size_t j = 0; j < n_size; ++j) {
            if (hay[i] == ndl[j]) return i;
        }
    }
    return (size_t)-1;
}

size_t __std_find_last_of_trivial_pos_1(const void* h, size_t h_size, const void* n, size_t n_size) {
    const unsigned char* hay = (const unsigned char*)h;
    const unsigned char* ndl = (const unsigned char*)n;
    for (size_t i = h_size; i > 0; --i) {
        for (size_t j = 0; j < n_size; ++j) {
            if (hay[i - 1] == ndl[j]) return i - 1;
        }
    }
    return (size_t)-1;
}

size_t __std_find_last_of_trivial_pos_2(const void* h, size_t h_size, const void* n, size_t n_size) {
    const unsigned short* hay = (const unsigned short*)h;
    const unsigned short* ndl = (const unsigned short*)n;
    for (size_t i = h_size; i > 0; --i) {
        for (size_t j = 0; j < n_size; ++j) {
            if (hay[i - 1] == ndl[j]) return i - 1;
        }
    }
    return (size_t)-1;
}

struct PtrPair __std_minmax_element_4(const int* first, const int* last) {
    struct PtrPair res;
    if (first == last) { res.p1 = first; res.p2 = first; return res; }
    const int* min_p = first;
    const int* max_p = first;
    for (++first; first != last; ++first) {
        if (*first < *min_p) min_p = first;
        if (*first > *max_p) max_p = first;
    }
    res.p1 = min_p; res.p2 = max_p;
    return res;
}

struct PtrPair __std_minmax_element_8(const long long* first, const long long* last) {
    struct PtrPair res;
    if (first == last) { res.p1 = first; res.p2 = first; return res; }
    const long long* min_p = first;
    const long long* max_p = first;
    for (++first; first != last; ++first) {
        if (*first < *min_p) min_p = first;
        if (*first > *max_p) max_p = first;
    }
    res.p1 = min_p; res.p2 = max_p;
    return res;
}

struct PtrPair __std_mismatch_1(const unsigned char* first1, const unsigned char* last1, const unsigned char* first2, const unsigned char* last2) {
    struct PtrPair res;
    while (first1 != last1 && first2 != last2 && *first1 == *first2) {
        ++first1;
        ++first2;
    }
    res.p1 = first1; res.p2 = first2;
    return res;
}

struct PtrPair __std_mismatch_8(const unsigned long long* first1, const unsigned long long* last1, const unsigned long long* first2, const unsigned long long* last2) {
    struct PtrPair res;
    while (first1 != last1 && first2 != last2 && *first1 == *first2) {
        ++first1;
        ++first2;
    }
    res.p1 = first1; res.p2 = first2;
    return res;
}

void __std_init_once_link_alternate_names_and_abort(void) {}
