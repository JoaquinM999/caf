// MSVC compatibility stubs for Visual Studio 2022 STL vector algorithms
// when building on environments with Visual Studio 2019 MSVC runtimes.
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

struct PtrPair {
    const void* p1;
    const void* p2;
};

const void* __std_find_trivial_1(const void* first, const void* last, uint8_t val) {
    const uint8_t* f = (const uint8_t*)first;
    const uint8_t* l = (const uint8_t*)last;
    for (; f != l; ++f) {
        if (*f == val) return f;
    }
    return l;
}

const void* __std_find_trivial_2(const void* first, const void* last, uint16_t val) {
    const uint16_t* f = (const uint16_t*)first;
    const uint16_t* l = (const uint16_t*)last;
    for (; f != l; ++f) {
        if (*f == val) return f;
    }
    return l;
}

const void* __std_find_trivial_4(const void* first, const void* last, uint32_t val) {
    const uint32_t* f = (const uint32_t*)first;
    const uint32_t* l = (const uint32_t*)last;
    for (; f != l; ++f) {
        if (*f == val) return f;
    }
    return l;
}

const void* __std_find_trivial_8(const void* first, const void* last, uint64_t val) {
    const uint64_t* f = (const uint64_t*)first;
    const uint64_t* l = (const uint64_t*)last;
    for (; f != l; ++f) {
        if (*f == val) return f;
    }
    return l;
}

const void* __std_find_last_trivial_1(const void* first, const void* last, uint8_t val) {
    const uint8_t* f = (const uint8_t*)first;
    const uint8_t* l = (const uint8_t*)last;
    while (l != f) {
        --l;
        if (*l == val) return l;
    }
    return (const uint8_t*)last;
}

const void* __std_find_last_trivial_2(const void* first, const void* last, uint16_t val) {
    const uint16_t* f = (const uint16_t*)first;
    const uint16_t* l = (const uint16_t*)last;
    while (l != f) {
        --l;
        if (*l == val) return l;
    }
    return (const uint16_t*)last;
}

void* __std_remove_1(void* first, void* last, uint8_t val) {
    uint8_t* f = (uint8_t*)first;
    uint8_t* l = (uint8_t*)last;
    uint8_t* out = f;
    for (; f != l; ++f) {
        if (*f != val) {
            *out++ = *f;
        }
    }
    return out;
}

void* __std_remove_2(void* first, void* last, uint16_t val) {
    uint16_t* f = (uint16_t*)first;
    uint16_t* l = (uint16_t*)last;
    uint16_t* out = f;
    for (; f != l; ++f) {
        if (*f != val) {
            *out++ = *f;
        }
    }
    return out;
}

void* __std_remove_8(void* first, void* last, uint64_t val) {
    uint64_t* f = (uint64_t*)first;
    uint64_t* l = (uint64_t*)last;
    uint64_t* out = f;
    for (; f != l; ++f) {
        if (*f != val) {
            *out++ = *f;
        }
    }
    return out;
}

size_t __std_count_trivial_4(const void* first, const void* last, uint32_t val) {
    const uint32_t* f = (const uint32_t*)first;
    const uint32_t* l = (const uint32_t*)last;
    size_t count = 0;
    for (; f != l; ++f) {
        if (*f == val) ++count;
    }
    return count;
}

size_t __std_count_trivial_8(const void* first, const void* last, uint64_t val) {
    const uint64_t* f = (const uint64_t*)first;
    const uint64_t* l = (const uint64_t*)last;
    size_t count = 0;
    for (; f != l; ++f) {
        if (*f == val) ++count;
    }
    return count;
}

const void* __std_min_element_4(const void* first, const void* last, bool is_signed) {
    if (first == last) return first;
    if (is_signed) {
        const int32_t* f = (const int32_t*)first;
        const int32_t* l = (const int32_t*)last;
        const int32_t* best = f;
        for (++f; f != l; ++f) {
            if (*f < *best) best = f;
        }
        return best;
    } else {
        const uint32_t* f = (const uint32_t*)first;
        const uint32_t* l = (const uint32_t*)last;
        const uint32_t* best = f;
        for (++f; f != l; ++f) {
            if (*f < *best) best = f;
        }
        return best;
    }
}

const void* __std_min_element_d(const double* first, const double* last, bool unused) {
    (void)unused;
    if (first == last) return first;
    const double* best = first;
    for (++first; first != last; ++first) {
        if (*first < *best) best = first;
    }
    return best;
}

const void* __std_min_element_f(const float* first, const float* last, bool unused) {
    (void)unused;
    if (first == last) return first;
    const float* best = first;
    for (++first; first != last; ++first) {
        if (*first < *best) best = first;
    }
    return best;
}

const void* __std_max_element_1(const void* first, const void* last, bool is_signed) {
    if (first == last) return first;
    if (is_signed) {
        const int8_t* f = (const int8_t*)first;
        const int8_t* l = (const int8_t*)last;
        const int8_t* best = f;
        for (++f; f != l; ++f) {
            if (*f > *best) best = f;
        }
        return best;
    } else {
        const uint8_t* f = (const uint8_t*)first;
        const uint8_t* l = (const uint8_t*)last;
        const uint8_t* best = f;
        for (++f; f != l; ++f) {
            if (*f > *best) best = f;
        }
        return best;
    }
}

const void* __std_max_element_4(const void* first, const void* last, bool is_signed) {
    if (first == last) return first;
    if (is_signed) {
        const int32_t* f = (const int32_t*)first;
        const int32_t* l = (const int32_t*)last;
        const int32_t* best = f;
        for (++f; f != l; ++f) {
            if (*f > *best) best = f;
        }
        return best;
    } else {
        const uint32_t* f = (const uint32_t*)first;
        const uint32_t* l = (const uint32_t*)last;
        const uint32_t* best = f;
        for (++f; f != l; ++f) {
            if (*f > *best) best = f;
        }
        return best;
    }
}

const void* __std_max_element_8(const void* first, const void* last, bool is_signed) {
    if (first == last) return first;
    if (is_signed) {
        const int64_t* f = (const int64_t*)first;
        const int64_t* l = (const int64_t*)last;
        const int64_t* best = f;
        for (++f; f != l; ++f) {
            if (*f > *best) best = f;
        }
        return best;
    } else {
        const uint64_t* f = (const uint64_t*)first;
        const uint64_t* l = (const uint64_t*)last;
        const uint64_t* best = f;
        for (++f; f != l; ++f) {
            if (*f > *best) best = f;
        }
        return best;
    }
}

const void* __std_max_element_d(const double* first, const double* last, bool unused) {
    (void)unused;
    if (first == last) return first;
    const double* best = first;
    for (++first; first != last; ++first) {
        if (*first > *best) best = first;
    }
    return best;
}

const void* __std_max_element_f(const float* first, const float* last, bool unused) {
    (void)unused;
    if (first == last) return first;
    const float* best = first;
    for (++first; first != last; ++first) {
        if (*first > *best) best = first;
    }
    return best;
}

int32_t __std_max_4i(const void* first, const void* last) {
    const int32_t* f = (const int32_t*)first;
    const int32_t* l = (const int32_t*)last;
    int32_t best = *f;
    for (++f; f != l; ++f) {
        if (*f > best) best = *f;
    }
    return best;
}

const void* __std_search_1(const void* first1, const void* last1, const void* first2, size_t count2) {
    const uint8_t* f1 = (const uint8_t*)first1;
    const uint8_t* l1 = (const uint8_t*)last1;
    const uint8_t* f2 = (const uint8_t*)first2;
    if (count2 == 0) return f1;
    size_t len1 = (size_t)(l1 - f1);
    if (len1 < count2) return l1;
    for (; f1 + count2 <= l1; ++f1) {
        if (memcmp(f1, f2, count2) == 0) return f1;
    }
    return l1;
}

const void* __std_search_2(const void* first1, const void* last1, const void* first2, size_t count2) {
    const uint16_t* f1 = (const uint16_t*)first1;
    const uint16_t* l1 = (const uint16_t*)last1;
    const uint16_t* f2 = (const uint16_t*)first2;
    if (count2 == 0) return f1;
    size_t len1 = (size_t)(l1 - f1);
    if (len1 < count2) return l1;
    for (; f1 + count2 <= l1; ++f1) {
        if (memcmp(f1, f2, count2 * sizeof(uint16_t)) == 0) return f1;
    }
    return l1;
}

const void* __std_find_end_1(const void* first1, const void* last1, const void* first2, size_t count2) {
    const uint8_t* f1 = (const uint8_t*)first1;
    const uint8_t* l1 = (const uint8_t*)last1;
    const uint8_t* f2 = (const uint8_t*)first2;
    if (count2 == 0) return l1;
    size_t len1 = (size_t)(l1 - f1);
    if (len1 < count2) return l1;
    const uint8_t* res = l1;
    for (; f1 + count2 <= l1; ++f1) {
        if (memcmp(f1, f2, count2) == 0) res = f1;
    }
    return res;
}

const void* __std_find_end_2(const void* first1, const void* last1, const void* first2, size_t count2) {
    const uint16_t* f1 = (const uint16_t*)first1;
    const uint16_t* l1 = (const uint16_t*)last1;
    const uint16_t* f2 = (const uint16_t*)first2;
    if (count2 == 0) return l1;
    size_t len1 = (size_t)(l1 - f1);
    if (len1 < count2) return l1;
    const uint16_t* res = l1;
    for (; f1 + count2 <= l1; ++f1) {
        if (memcmp(f1, f2, count2 * sizeof(uint16_t)) == 0) res = f1;
    }
    return res;
}

size_t __std_find_first_of_trivial_pos_1(const void* h, size_t h_size, const void* n, size_t n_size) {
    const uint8_t* hay = (const uint8_t*)h;
    const uint8_t* ndl = (const uint8_t*)n;
    for (size_t i = 0; i < h_size; ++i) {
        for (size_t j = 0; j < n_size; ++j) {
            if (hay[i] == ndl[j]) return i;
        }
    }
    return (size_t)-1;
}

size_t __std_find_first_of_trivial_pos_2(const void* h, size_t h_size, const void* n, size_t n_size) {
    const uint16_t* hay = (const uint16_t*)h;
    const uint16_t* ndl = (const uint16_t*)n;
    for (size_t i = 0; i < h_size; ++i) {
        for (size_t j = 0; j < n_size; ++j) {
            if (hay[i] == ndl[j]) return i;
        }
    }
    return (size_t)-1;
}

size_t __std_find_last_of_trivial_pos_1(const void* h, size_t h_size, const void* n, size_t n_size) {
    const uint8_t* hay = (const uint8_t*)h;
    const uint8_t* ndl = (const uint8_t*)n;
    for (size_t i = h_size; i > 0; --i) {
        for (size_t j = 0; j < n_size; ++j) {
            if (hay[i - 1] == ndl[j]) return i - 1;
        }
    }
    return (size_t)-1;
}

size_t __std_find_last_of_trivial_pos_2(const void* h, size_t h_size, const void* n, size_t n_size) {
    const uint16_t* hay = (const uint16_t*)h;
    const uint16_t* ndl = (const uint16_t*)n;
    for (size_t i = h_size; i > 0; --i) {
        for (size_t j = 0; j < n_size; ++j) {
            if (hay[i - 1] == ndl[j]) return i - 1;
        }
    }
    return (size_t)-1;
}

struct PtrPair __std_minmax_element_4(const void* first, const void* last, bool is_signed) {
    struct PtrPair res;
    if (first == last) { res.p1 = first; res.p2 = first; return res; }
    if (is_signed) {
        const int32_t* f = (const int32_t*)first;
        const int32_t* l = (const int32_t*)last;
        const int32_t* min_p = f;
        const int32_t* max_p = f;
        for (++f; f != l; ++f) {
            if (*f < *min_p) min_p = f;
            else if (*f >= *max_p) max_p = f;
        }
        res.p1 = min_p; res.p2 = max_p;
    } else {
        const uint32_t* f = (const uint32_t*)first;
        const uint32_t* l = (const uint32_t*)last;
        const uint32_t* min_p = f;
        const uint32_t* max_p = f;
        for (++f; f != l; ++f) {
            if (*f < *min_p) min_p = f;
            else if (*f >= *max_p) max_p = f;
        }
        res.p1 = min_p; res.p2 = max_p;
    }
    return res;
}

struct PtrPair __std_minmax_element_8(const void* first, const void* last, bool is_signed) {
    struct PtrPair res;
    if (first == last) { res.p1 = first; res.p2 = first; return res; }
    if (is_signed) {
        const int64_t* f = (const int64_t*)first;
        const int64_t* l = (const int64_t*)last;
        const int64_t* min_p = f;
        const int64_t* max_p = f;
        for (++f; f != l; ++f) {
            if (*f < *min_p) min_p = f;
            else if (*f >= *max_p) max_p = f;
        }
        res.p1 = min_p; res.p2 = max_p;
    } else {
        const uint64_t* f = (const uint64_t*)first;
        const uint64_t* l = (const uint64_t*)last;
        const uint64_t* min_p = f;
        const uint64_t* max_p = f;
        for (++f; f != l; ++f) {
            if (*f < *min_p) min_p = f;
            else if (*f >= *max_p) max_p = f;
        }
        res.p1 = min_p; res.p2 = max_p;
    }
    return res;
}

size_t __std_mismatch_1(const void* first1, const void* first2, size_t count) {
    const uint8_t* f1 = (const uint8_t*)first1;
    const uint8_t* f2 = (const uint8_t*)first2;
    for (size_t i = 0; i < count; ++i) {
        if (f1[i] != f2[i]) return i;
    }
    return count;
}

size_t __std_mismatch_8(const void* first1, const void* first2, size_t count) {
    const uint64_t* f1 = (const uint64_t*)first1;
    const uint64_t* f2 = (const uint64_t*)first2;
    for (size_t i = 0; i < count; ++i) {
        if (f1[i] != f2[i]) return i;
    }
    return count;
}

void __std_init_once_link_alternate_names_and_abort(void) {}
