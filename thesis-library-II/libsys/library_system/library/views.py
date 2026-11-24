import copy
import re
import csv
import datetime
import pandas as pd
from collections import defaultdict

from django import template
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Case, When, Value, IntegerField
from django.forms.models import model_to_dict
from django.core.paginator import Paginator

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from .forms import BibliographyEntryForm, UploadFileForm
from .models import BibliographyEntry


# -------------------------------------------------------------------------------------------------
# GLOBAL MODEL & DICTIONARY INITIALIZATIONS (LAZY LOADED)
# -------------------------------------------------------------------------------------------------

_sbert_model = None
_lemmatizer = None
_stemmer = None

def get_sbert_model():
    global _sbert_model
    if _sbert_model is None:
        from sentence_transformers import SentenceTransformer
        _sbert_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _sbert_model

def get_lemmatizer():
    global _lemmatizer
    if _lemmatizer is None:
        from nltk.stem import WordNetLemmatizer
        _lemmatizer = WordNetLemmatizer()
    return _lemmatizer

def get_stemmer():
    global _stemmer
    if _stemmer is None:
        from nltk.stem import PorterStemmer
        _stemmer = PorterStemmer()
    return _stemmer


stop_words = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no",
    "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd",
    "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that",
    "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what",
    "what's", "when", "when's", "where", "where's", "which", "while", "who",
    "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you",
    "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves",
}


DEPARTMENT_MAP = {
    "caresdept": ["College of Agriculture, Resources and Environmental Sciences", "CARES", "Agriculture"],
    "casdept": ["College of Arts and Sciences", "CAS", "Arts and Sciences"],
    "cbadept": ["College of Business and Accountancy", "CBA", "Business and Accountancy", "Accountancy"],
    "cssdept": ["College of Computer Studies", "CCS", "Computer Studies", "CCS-BLIS"],
    "coeddept": ["College of Education", "COED", "CED", "Education"],
    "coedept": ["College of Engineering", "COE", "Engineering"],
    "chmdept": ["College of Hospitality Management", "CHM", "Hospitality Management"],
    "lawdept": ["College of Law", "COL", "Law"],
    "cmlsdept": ["College of Medical Laboratory Sciences", "CMLS", "Medical Laboratory Sciences", "MedTech"],
    "condept": ["College of Nursing", "CON", "Nursing"],
    "copdept": ["College of Pharmacy", "COP", "Pharmacy"],
    "theologydept": ["College of Theology", "COT", "Theology"],
    "elemdept": ["Elementary", "ELEM", "Grade School"],
    "jhsdept": ["Junior High School", "JHS", "High School"],
    "kinderdept": ["Kindergarten", "KINDER", "Preschool"],
    "sgsdept": ["School of Graduate Studies", "SGS", "Graduate Studies", "Grad School"],
    "shsdept": ["Senior High School", "SHS"],
}



# -------------------------------------------------------------------------------------------------
# USER ROLES & PERMISSION
# -------------------------------------------------------------------------------------------------

def is_librarian(user):
    return user.groups.filter(name="Librarian").exists()


def is_department(user):
    return user.groups.filter(name="Department").exists()


def get_auto_departments(user):
    if not user or not user.is_authenticated:
        return []

    group_names = {group.name.lower().strip() for group in user.groups.all()}

    department_map = {
        "caresdept": ["College of Agriculture, Resources and Environmental Sciences", "CARES", "Agriculture"],
        "casdept": ["College of Arts and Sciences", "CAS", "Arts and Sciences"],
        "cbadept": ["College of Business and Accountancy", "CBA", "Business and Accountancy", "Accountancy"],
        "cssdept": ["College of Computer Studies", "CCS", "Computer Studies", "CCS-BLIS"],
        "coeddept": ["College of Education", "COED", "CED", "Education"],
        "coedept": ["College of Engineering", "COE", "Engineering"],
        "chmdept": ["College of Hospitality Management", "CHM", "Hospitality Management"],
        "lawdept": ["College of Law", "COL", "Law"],
        "cmlsdept": ["College of Medical Laboratory Sciences", "CMLS", "Medical Laboratory Sciences", "MedTech"],
        "condept": ["College of Nursing", "CON", "Nursing"],
        "copdept": ["College of Pharmacy", "COP", "Pharmacy"],
        "theologydept": ["College of Theology", "COT", "Theology"],
        "elemdept": ["Elementary", "ELEM", "Grade School"],
        "jhsdept": ["Junior High School", "JHS", "High School"],
        "kinderdept": ["Kindergarten", "KINDER", "Preschool"],
        "sgsdept": ["School of Graduate Studies", "SGS", "Graduate Studies", "Grad School"],
        "shsdept": ["Senior High School", "SHS"],
    }

    auto_depts = []
    for key, aliases in department_map.items():
        if key in group_names or any(alias.lower() in group_names for alias in aliases):
            auto_depts.extend(aliases)

    return list(set(auto_depts))



# -------------------------------------------------------------------------------------------------
# ACQUISITION DATABASE FILTERING & SORTING HELPERS
# -------------------------------------------------------------------------------------------------

def get_base_entries():
    return BibliographyEntry.objects.all()


def apply_search(entries, query):
    if not query:
        return entries
    qobj = (
        Q(title__icontains=query)
        | Q(author__icontains=query)
        | Q(publisher__icontains=query)
        | Q(isbn__icontains=query)
        | Q(accession_number__icontains=query)
    )
    return entries.filter(qobj)


def apply_filters(entries, years, recommended_bys, departments, sections):
    return filter_entries(
        entries,
        years=[int(y) for y in years if y.isdigit()] or None,
        recommended_bys=recommended_bys or None,
        departments=departments or None,
        sections=sections or None,
    )


def filter_entries(entries, years=None, recommended_bys=None, departments=None, sections=None):
    if years:
        entries = entries.filter(year__in=years)
    if recommended_bys:
        q = Q()
        for rb in recommended_bys:
            q |= Q(recommended_by__icontains=rb)
        entries = entries.filter(q)
    if departments:
        q = Q()
        for d in departments:
            aliases = [d]
            for dept_key, dept_aliases in DEPARTMENT_MAP.items():
                if any(d.lower() == alias.lower() for alias in dept_aliases):
                    aliases = dept_aliases
                    break
            
            for alias in aliases:
                q |= Q(department__icontains=alias)
                
        entries = entries.filter(q)
    if sections:
        q = Q()
        for s in sections:
            q |= Q(section__icontains=s)
        entries = entries.filter(q)

    return entries


def sort_entries(entries, sort_field, sort_order, has_auto_dept=False):
    if not sort_field:
        return entries
        
    prefix = "-" if sort_order == "desc" else ""
    field_name = f"{prefix}{sort_field}"

    if has_auto_dept:
        return entries.order_by("dept_priority", field_name)
    
    return entries.order_by(field_name)


def prioritize_departments(entries, auto_departments):
    if not auto_departments:
        return entries
    return entries.annotate(
        dept_priority=Case(
            When(department__in=auto_departments, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("dept_priority")


def paginate_entries(entries, page_number, per_page=20):
    paginator = Paginator(entries, per_page)
    return paginator.get_page(page_number)



# -------------------------------------------------------------------------------------------------
# NLP & MATCHING ALGORITHM HELPERS
# -------------------------------------------------------------------------------------------------

CACHED_ENTRY_IDS = []
CACHED_BOOK_EMBEDDINGS = None
CACHED_JACCARD_TITLES = {}

def update_embedding_cache():
    global CACHED_ENTRY_IDS, CACHED_BOOK_EMBEDDINGS, CACHED_JACCARD_TITLES
    entries = list(BibliographyEntry.objects.all().only("id", "title"))
    if not entries:
        return
    
    CACHED_ENTRY_IDS = [e.id for e in entries]
    titles = [str(getattr(e, "title", "") or "") for e in entries]
    
    # Precompute SBERT embeddings
    sbert_model = get_sbert_model()
    CACHED_BOOK_EMBEDDINGS = sbert_model.encode(titles, convert_to_tensor=True)

    # Precompute Jaccard tokens once during caching to prevent repeated regex processing
    CACHED_JACCARD_TITLES = {e.id: preprocess_jaccard(e.title) for e in entries}
    

def preprocess_jaccard(text):
    if text is None:
        return ""
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    tokens = text.split()
    
    clean_stop_words = {re.sub(r"[^a-z0-9]", "", w) for w in stop_words}
    stemmer = get_stemmer()
    
    duplicate = set()
    unique_tokens = []
    for t in tokens:
        t = stemmer.stem(t)
        
        if t not in clean_stop_words and t not in duplicate:
            duplicate.add(t)
            unique_tokens.append(t)
            
    return " ".join(unique_tokens)


def jaccard_similarity(query, entry):
    if not query:
        query = ""
    if not entry:
        entry = ""
    set_a = set(query.lower().split())
    set_b = set(entry.lower().split())
    intersection = set_a.intersection(set_b)
    union = set_a.union(set_b)
    
    if not union:
        return 0.0
        
    return len(intersection) / len(union)


def sbert_similarity(query, entry):
    from sentence_transformers import util
    text = " ".join(
        [
            str(getattr(entry, "title", "")),
        ]
    )
    sbert_model = get_sbert_model()
    query_emb = sbert_model.encode(query)
    entry_emb = sbert_model.encode(text)
    return util.cos_sim(query_emb, entry_emb).item()


def jaccard_sbert_hybrid(score_sbert, score_jaccard, w_sbert=0.7, w_jaccard=0.3):
    final_score = (w_sbert * score_sbert) + (w_jaccard * score_jaccard)
    
    return float(min(1.0, max(0.0, final_score)))


def compute_scores_batch_optimized(course_queries, query_embs, entries_list, top_k_sbert=50):
    from sentence_transformers import util
    import torch
    global CACHED_BOOK_EMBEDDINGS, CACHED_ENTRY_IDS, CACHED_JACCARD_TITLES
    
    if CACHED_BOOK_EMBEDDINGS is None:
        update_embedding_cache()

    if CACHED_BOOK_EMBEDDINGS is None or len(CACHED_BOOK_EMBEDDINGS) == 0:
        return []

    cos_sim_matrix = util.cos_sim(query_embs, CACHED_BOOK_EMBEDDINGS)

    all_course_results = []

    for i, query in enumerate(course_queries):
        query_scores = cos_sim_matrix[i]
        
        k = min(top_k_sbert, query_scores.shape[0])
        top_scores, top_indices = torch.topk(query_scores, k=k)
        
        query_jacc = preprocess_jaccard(query)
        course_matches = []

        for score_tensor, idx_tensor in zip(top_scores, top_indices):
            score_sbert = max(0.0, float(score_tensor.item()))
            entry_id = CACHED_ENTRY_IDS[idx_tensor.item()]
            
            title_jacc = CACHED_JACCARD_TITLES.get(entry_id, "")
            score_jaccard = max(0.0, float(jaccard_similarity(query_jacc, title_jacc)))

            final_score = jaccard_sbert_hybrid(score_sbert, score_jaccard)

            if final_score > 0.1:
                course_matches.append({
                    "entry_id": entry_id,
                    "jaccard": score_jaccard,
                    "sbert": score_sbert,
                    "jaccard_sbert": final_score,
                })

        course_matches.sort(key=lambda x: x["jaccard_sbert"], reverse=True)
        all_course_results.append(course_matches)

    return all_course_results


def compute_scores_batch(query, query_emb, entries_list, sbert_cutoff=0.25):
    from sentence_transformers import util
    global CACHED_BOOK_EMBEDDINGS, CACHED_ENTRY_IDS, CACHED_JACCARD_TITLES
    
    if not query or not entries_list:
        return []

    if CACHED_BOOK_EMBEDDINGS is None:
        update_embedding_cache()

    sbert_scores = util.cos_sim(query_emb, CACHED_BOOK_EMBEDDINGS)[0].tolist()
    query_jacc = preprocess_jaccard(query)
    id_to_score = dict(zip(CACHED_ENTRY_IDS, sbert_scores))
    
    results = []
    for entry in entries_list:
        score_sbert = max(0.0, float(id_to_score.get(entry.id, 0.0)))

        if score_sbert < sbert_cutoff:
            continue

        title_jacc = CACHED_JACCARD_TITLES.get(entry.id) or preprocess_jaccard(entry.title)
        score_jaccard = max(0.0, float(jaccard_similarity(query_jacc, title_jacc)))

        final_score = jaccard_sbert_hybrid(score_sbert, score_jaccard)

        results.append({
            "entry": entry,
            "jaccard": score_jaccard,
            "sbert": score_sbert,
            "jaccard_sbert": final_score,
        })

    return results



# -------------------------------------------------------------------------------------------------
# BIBLIOGRAPHY & SUMMARY TREE BUILDING HELPERS
# -------------------------------------------------------------------------------------------------

def parse_selected_items(raw_selected, search_query="General Search"):
    parsed_items = []
    is_batch_mode = False

    for item in raw_selected:
        item_str = str(item)

        if "|" in item_str:
            parts = item_str.split("|")
            entry_id = parts[0]
            year_level = (
                parts[1].strip() if len(parts) > 1 and parts[1].strip() else "GENERAL"
            )
            semester = (
                parts[2].strip()
                if len(parts) > 2 and parts[2].strip()
                else "General Term"
            )
            course_code = (
                parts[3].strip() if len(parts) > 3 and parts[3].strip() else "SEARCH"
            )
            course_title = (
                parts[4].strip()
                if len(parts) > 4 and parts[4].strip()
                else f'Search Results for "{search_query}"'
            )
            is_batch_mode = True
        else:
            entry_id = item_str
            year_level = "GENERAL SEARCH"
            semester = "Results"
            course_code = "QUERY"
            course_title = f'Search Term: "{search_query}"'

        if entry_id.isdigit():
            try:
                entry = BibliographyEntry.objects.get(id=int(entry_id))
                parsed_items.append(
                    {
                        "entry": entry,
                        "year_level": year_level,
                        "semester": semester,
                        "course_code": course_code,
                        "course_title": course_title,
                    }
                )
            except BibliographyEntry.DoesNotExist:
                continue

    return parsed_items, is_batch_mode


def build_bibliography_tree(parsed_items):
    raw_grouped = {}

    for item in parsed_items:
        yl = item["year_level"]
        sem = item["semester"]
        title = item["course_title"]
        entry = item["entry"]

        if yl not in raw_grouped:
            raw_grouped[yl] = {}
        if sem not in raw_grouped[yl]:
            raw_grouped[yl][sem] = {}
        if title not in raw_grouped[yl][sem]:
            raw_grouped[yl][sem][title] = []

        raw_grouped[yl][sem][title].append(entry)

    processed_grouped = {}
    for yl, semesters in raw_grouped.items():
        processed_grouped[yl] = {}
        for sem, courses in semesters.items():
            processed_grouped[yl][sem] = {}
            for course_title, entries in courses.items():
                years = [
                    e.year
                    for e in entries
                    if hasattr(e, "year") and e.year and str(e.year).isdigit()
                ]
                if years:
                    min_y, max_y = min(years), max(years)
                    year_range = f"{min_y}–{max_y}" if min_y != max_y else str(min_y)
                else:
                    year_range = "N/A"

                processed_grouped[yl][sem][course_title] = {
                    "entries": entries,
                    "year_range": year_range,
                }

    return processed_grouped


def build_summary_tree(parsed_items):
    summary_tree = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for item in parsed_items:
        yl = item["year_level"]
        sem = item["semester"]
        code = item["course_code"]
        title = item["course_title"]
        entry = item["entry"]

        summary_tree[yl][sem][(code, title)].append(entry)

    processed_summary = {}
    grand_total_t = 0
    grand_total_v = 0
    all_years = []

    for yl, semesters in summary_tree.items():
        processed_summary[yl] = {}

        for sem, courses in semesters.items():
            processed_summary[yl][sem] = {
                "courses": [],
                "sem_total_t": 0,
                "sem_total_v": 0,
            }
            sem_years = []

            for (c_code, c_title), entries in courses.items():
                t_count = len(entries)
                v_count = sum([1 for e in entries])

                years = [
                    e.year
                    for e in entries
                    if hasattr(e, "year") and e.year and str(e.year).isdigit()
                ]
                sem_years.extend(years)
                all_years.extend(years)

                processed_summary[yl][sem]["courses"].append(
                    {
                        "course_code": c_code,
                        "course_title": c_title,
                        "t_count": t_count,
                        "v_count": v_count,
                    }
                )

                processed_summary[yl][sem]["sem_total_t"] += t_count
                processed_summary[yl][sem]["sem_total_v"] += v_count

            if sem_years:
                min_y, max_y = min(sem_years), max(sem_years)
                processed_summary[yl][sem]["year_range"] = (
                    f"Copyright {min_y}–{max_y}"
                    if min_y != max_y
                    else f"Copyright {min_y}"
                )
            else:
                processed_summary[yl][sem]["year_range"] = "No Publication Date"

            grand_total_t += processed_summary[yl][sem]["sem_total_t"]
            grand_total_v += processed_summary[yl][sem]["sem_total_v"]

    overall_range = (
        f"{min(all_years)}–{max(all_years)}"
        if all_years and min(all_years) != max(all_years)
        else (str(all_years[0]) if all_years else "N/A")
    )

    return {
        "summary_data": processed_summary,
        "grand_total_t": grand_total_t,
        "grand_total_v": grand_total_v,
        "overall_range": overall_range,
    }



# -------------------------------------------------------------------------------------------------
# AUTHENTICATION & CORE NAVIGATION VIEWS
# -------------------------------------------------------------------------------------------------

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("home")
        else:
            return render(request, "login-page.html", {"error": "Invalid credentials"})
    return render(request, "login-page.html")


def logout_view(request):
    logout(request)
    return render(request, "index-page.html")


def profile_page(request):
    return render(request, "profile-page.html")


def home(request):
    is_librarian = False
    if request.user.is_authenticated:
        is_librarian = request.user.groups.filter(name="Librarian").exists()
    return render(request, "index-page.html", {"is_librarian": is_librarian})


# -------------------------------------------------------------------------------------------------
# ACQUISITION
# -------------------------------------------------------------------------------------------------

def invalidate_embedding_cache():
    global CACHED_BOOK_EMBEDDINGS, CACHED_ENTRY_IDS
    CACHED_BOOK_EMBEDDINGS = None
    CACHED_ENTRY_IDS = []


@login_required
@user_passes_test(is_librarian)
def encoding_page(request):
    message = None
    is_success = False
        
    if request.method == "POST":
        form = BibliographyEntryForm(request.POST)
        if form.is_valid():
            form.save()
            
            invalidate_embedding_cache()
            
            form = BibliographyEntryForm()
            message = "Entry successfully added!"
            is_success = True
        else:
            message = "Please make sure all necessary fields are properly filled."
    else:
        form = BibliographyEntryForm()

    is_librarian = request.user.groups.filter(name="Librarian").exists()
    return render(
        request,
        "encoding-page.html",
        {
            "form": form,
            "message": message,
            "is_librarian": is_librarian,
        },
    )


def acquisition_page(request):
    query = request.GET.get("q", "").strip()
    selected_years = request.GET.getlist("year")
    selected_recommended_bys = request.GET.getlist("recommended_by")
    selected_departments = request.GET.getlist("department")
    selected_sections = request.GET.getlist("section")
    sort_field = request.GET.get("sort_field")
    sort_order = request.GET.get("sort_order", "asc")

    is_librarian = (
        request.user.groups.filter(name="Librarian").exists()
        if request.user.is_authenticated
        else False
    )

    auto_departments = get_auto_departments(request.user)
    entries = get_base_entries()

    entries = apply_filters(
        entries,
        selected_years,
        selected_recommended_bys,
        selected_departments,
        selected_sections,
    )

    entries = prioritize_departments(entries, auto_departments)

    display_list = []

    if query:
        entries_list = list(entries)
        sbert_model = get_sbert_model()
        query_emb = sbert_model.encode(str(query), convert_to_tensor=True)
        
        # Batch compute scores instantly
        all_scored = compute_scores_batch(query, query_emb, entries_list)
        
        scored = [item for item in all_scored if item["jaccard_sbert"] > 0.3]

        if sort_field:
            reverse_sort = sort_order == "desc"
            scored.sort(key=lambda item: getattr(item["entry"], sort_field, "") or "", reverse=reverse_sort)
        else:
            scored.sort(key=lambda x: x["jaccard_sbert"], reverse=True)

        display_list = scored
    else:
        if sort_field:
            entries = sort_entries(entries, sort_field, sort_order, has_auto_dept=bool(auto_departments))
        else:
            entries = entries.order_by("dept_priority", "-id") if auto_departments else entries.order_by("-id")

        display_list = [{"entry": e, "jaccard_sbert": 0.0} for e in entries]

    paginator = Paginator(display_list, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "acquisition-page.html",
        {
            "query": query,
            "selected_years": selected_years,
            "selected_recommended_bys": selected_recommended_bys,
            "selected_departments": selected_departments or auto_departments,
            "selected_sections": selected_sections,
            "auto_departments": auto_departments,
            "page_obj": page_obj,
            "is_librarian": is_librarian,
        },
    )


@login_required
@user_passes_test(is_librarian)
def acquisition_batch_page(request):
    is_librarian = request.user.groups.filter(name="Librarian").exists()
    results = []

    if request.method == "POST":
        uploaded_file = request.FILES.get("subject_list")
        if uploaded_file and (uploaded_file.name.endswith(".xlsx") or uploaded_file.name.endswith(".xls")):
            import openpyxl
            wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
            ws = wb.active

            rows = list(ws.iter_rows(min_row=2, values_only=True))
            parsed_courses = []
            full_texts = []

            for row in rows:
                if not row or not any(row):
                    continue

                year_level = str(row[0] or "").strip()
                semester = str(row[1] or "").strip()
                course_code = str(row[2] or "").strip()
                course_title = str(row[3] or "").strip()
                course_description = str(row[4] or "").strip()

                if not course_title:
                    continue

                full_course_text = f"{course_title} {course_description}".strip()
                parsed_courses.append({
                    "year_level": year_level,
                    "semester": semester,
                    "course_code": course_code,
                    "course_title": course_title,
                    "course_description": course_description,
                })
                full_texts.append(full_course_text)

            if parsed_courses:
                sbert_model = get_sbert_model()
                query_embs = sbert_model.encode(full_texts, convert_to_tensor=True, batch_size=32)

                entries_list = list(BibliographyEntry.objects.all().only("id", "title"))
                course_titles = [c["course_title"] for c in parsed_courses]
                
                batched_matches = compute_scores_batch_optimized(course_titles, query_embs, entries_list)

                for course_info, matches in zip(parsed_courses, batched_matches):
                    results.append({
                        "id": course_info["course_title"],
                        "code": course_info["course_code"],
                        "course_code": course_info["course_code"],
                        "course_title": course_info["course_title"],
                        "course_description": course_info["course_description"],
                        "year_level": course_info["year_level"],
                        "semester": course_info["semester"],
                        "matches": matches[:15], # Limit stored matches per course to prevent session bloatedness
                    })

        request.session["batch_results"] = results
    else:
        results = request.session.get("batch_results", [])

    render_results = copy.deepcopy(results)

    if render_results:
        all_entry_ids = {
            m["entry_id"]
            for course in render_results
            for m in course.get("matches", [])
        }
        
        entries_dict = BibliographyEntry.objects.filter(id__in=all_entry_ids).only(
            "id", "title", "author", "year", "publisher", "accession_number"
        ).in_bulk()

        for course in render_results:
            for match in course.get("matches", []):
                match["entry"] = entries_dict.get(match["entry_id"])

    return render(
        request,
        "acquisition-batch-page.html",
        {
            "results": render_results,
            "is_librarian": is_librarian,
        },
    )


@login_required
@user_passes_test(is_librarian)
def acquisition_import_page(request):
    return render(request, "acquisition-import.html")


def full_details_page(request, entry_id):
    entry = get_object_or_404(BibliographyEntry, id=entry_id)
    is_librarian = (
        request.user.groups.filter(name="Librarian").exists()
        if request.user.is_authenticated
        else False
    )
    return render(
        request, "full-details.html", {"entry": entry, "is_librarian": is_librarian}
    )


@login_required
@user_passes_test(is_librarian)
def edit_entry(request, entry_id):
    entry = get_object_or_404(BibliographyEntry, id=entry_id)
    
    if request.method == "POST":
        form = BibliographyEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            invalidate_embedding_cache()
            return redirect("full_details", entry_id=entry.id)
        else:
            print("Form validation failed:", form.errors)
    else:
        form = BibliographyEntryForm(instance=entry)

    is_librarian = request.user.groups.filter(name="Librarian").exists()
    return render(
        request,
        "encoding-page.html",
        {
            "form": form,
            "entry": entry,
            "is_librarian": is_librarian,
        },
    )


@login_required
@user_passes_test(is_librarian)
def delete_entry(request, entry_id):
    entry = get_object_or_404(BibliographyEntry, id=entry_id)
    if request.method == "POST":
        entry.delete()
        invalidate_embedding_cache()
        return redirect("acquisition")
    return render(request, "confirm_delete.html", {"entry": entry})


@login_required
@user_passes_test(is_librarian)
def import_page(request):
    form = UploadFileForm()
    return render(request, "import-page.html", {"form": form})


@login_required
@user_passes_test(is_librarian)
def import_books(request):
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "cancel":
            request.session.pop("import_preview", None)
            request.session.pop("import_filename", None)
            return redirect("import_page")

        if action == "preview":
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = request.FILES["file"]
                df = pd.read_excel(excel_file, keep_default_na=False)
                df = df.where(pd.notnull(df), None)
                
                preview_list = []
                for _, row in df.iterrows():
                    if row.get("title") and row.get("author"):
                        preview_list.append({
                            "accession_number": row.get("accession_number", ""),
                            "call_number": row.get("call_number", ""),
                            "author": row.get("author", ""),
                            "title": row.get("title", ""),
                            "edition": row.get("edition", ""),
                            "volume": row.get("volume", ""),
                            "publisher": row.get("publisher", ""),
                            "year": row.get("year", ""),
                            "isbn": row.get("isbn", ""),
                            "department": row.get("department", ""),
                        })

                request.session["import_preview"] = preview_list
                request.session["import_filename"] = excel_file.name

                return render(request, "import-page.html", {
                    "form": form,
                    "filename": excel_file.name,
                    "preview": preview_list
                })

        elif action == "confirm":
            preview_list = request.session.get("import_preview", [])
            for row in preview_list:
                if not BibliographyEntry.objects.filter(accession_number=row["accession_number"]).exists():
                    BibliographyEntry.objects.create(
                        accession_number=row["accession_number"],
                        call_number=row["call_number"],
                        author=row["author"],
                        title=row["title"],
                        edition=row["edition"],
                        volume=row["volume"],
                        publisher=row["publisher"],
                        year=row["year"],
                        isbn=row["isbn"],
                        department=row["department"],
                    )
            
            request.session.pop("import_preview", None)
            request.session.pop("import_filename", None)
            return redirect("acquisition")

    else:
        form = UploadFileForm()

    return render(request, "import-page.html", {"form": form})



# -------------------------------------------------------------------------------------------------
# ALGORITHM BENCHMARK & TEST VIEWS
# -------------------------------------------------------------------------------------------------

def algo_result(request):
    encoded_entries = BibliographyEntry.objects.all()
    query = request.GET.get("q", "")
    mode = request.GET.get("mode", "")

    results = []
    if query:
        sbert_model = get_sbert_model()
        query_emb = sbert_model.encode(str(query))

        for entry in encoded_entries:
            scores_list = compute_scores_batch(query, query_emb, [entry])
            if not scores_list:
                continue
            score = scores_list[0]

            if mode == "jaccard":
                final_score = score["jaccard"]
            elif mode == "sbert":
                final_score = score["sbert"]
            else:
                final_score = score["jaccard_sbert"]

            if final_score > 0.25:
                results.append(
                    (
                        entry,
                        score["jaccard"],
                        score["sbert"],
                        score["jaccard_sbert"],
                    )
                )

        if mode == "jaccard":
            results.sort(key=lambda x: x[1], reverse=True)
        elif mode == "sbert":
            results.sort(key=lambda x: x[2], reverse=True)
        else:
            results.sort(key=lambda x: x[3], reverse=True)

    return render(
        request, "algo-result.html", {"results": results, "query": query, "mode": mode}
    )



# -------------------------------------------------------------------------------------------------
# BIBLIOGRAPHY, SUMMARY & EXPORT VIEWS
# -------------------------------------------------------------------------------------------------

def bibliography_page(request, course_code=None):
    if request.method == "POST":
        raw_selected = request.POST.getlist("selected_entries") or request.POST.getlist(
            "ids"
        )
    else:
        raw_selected = (
            request.GET.getlist("selected_entries")
            or request.GET.getlist("selected_matches")
            or request.GET.getlist("ids")
        )

    search_query = request.GET.get("q") or request.POST.get("q") or ""
    program_name = (
        request.POST.get("program_name")
        or "BACHELOR OF LIBRARY INFORMATION SCIENCE (BLIS)"
    )
    college_name = request.POST.get("college_name") or "COMPUTER STUDIES"

    parsed_items, is_batch_mode = parse_selected_items(
        raw_selected, search_query=search_query
    )

    grouped_data = build_bibliography_tree(parsed_items)
    summary_metrics = build_summary_tree(parsed_items)

    is_librarian = (
        request.user.groups.filter(name="Librarian").exists()
        if request.user.is_authenticated
        else False
    )
    is_department = (
        request.user.groups.filter(name="Department").exists()
        if request.user.is_authenticated
        else False
    )

    context = {
        "grouped_data": grouped_data,
        "summary_data": summary_metrics["summary_data"],
        "grand_total_t": summary_metrics["grand_total_t"],
        "grand_total_v": summary_metrics["grand_total_v"],
        "overall_range": summary_metrics["overall_range"],
        "program_name": program_name,
        "college_name": college_name,
        "is_batch_mode": is_batch_mode,
        "search_query": search_query,
        "is_librarian": is_librarian,
        "is_department": is_department,
        "raw_selected": raw_selected,
    }

    return render(request, "bibliography-page.html", context)


def summary_page(request):
    is_librarian = request.user.groups.filter(name="Librarian").exists()
    is_department = request.user.groups.filter(name="Department").exists()
    return render(
        request,
        "summary-page.html",
        {"is_librarian": is_librarian, "is_department": is_department},
    )


@login_required
@user_passes_test(is_librarian)
def export_file(request):
    if request.method == "POST":
        raw_selected = request.POST.getlist("selected_entries") or request.POST.getlist("ids")
        export_type = request.POST.get("export_type", "pdf").lower()
        target_page = request.POST.get("target_page", "all").lower()
    else:
        raw_selected = request.GET.getlist("ids") or request.GET.getlist("selected_entries")
        export_type = request.GET.get("export_type", "pdf").lower()
        target_page = request.GET.get("target_page", "all").lower()

    selected_ids = []
    for item in raw_selected:
        clean_id = str(item).split("|")[0].strip()
        if clean_id.isdigit():
            selected_ids.append(int(clean_id))

    if selected_ids:
        entries = BibliographyEntry.objects.filter(id__in=selected_ids)
    else:
        entries = BibliographyEntry.objects.all()

    all_fields = [
        "id", "date_received", "accession_number", "call_number", "title",
        "year", "author", "edition", "volume", "pages", "dealer", "price",
        "place_of_publication", "publisher", "isbn", "recommended_by",
        "department", "section", "budget_charge", "po_number", "si_number", "contents"
    ]

    # CSV EXPORT
    if export_type == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="report.csv"'

        writer = csv.writer(response)
        writer.writerow([f.replace("_", " ").title() for f in all_fields])

        for entry in entries:
            writer.writerow([getattr(entry, field, "") for field in all_fields])
        return response

    # EXCEL EXPORT
    if export_type == "xlsx":
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Bibliography Report"

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="02062C", end_color="02062C", fill_type="solid")

        headers = [f.replace("_", " ").title() for f in all_fields]
        ws.append(headers)

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        for entry in entries:
            ws.append([getattr(entry, field, "") for field in all_fields])

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="report.xlsx"'
        wb.save(response)
        return response

    # PDF EXPORT
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="report.pdf"'

    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    y = height - 50

    if target_page in ["biblio", "all"]:
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Bibliography Report")
        y -= 30
        p.setFont("Helvetica", 11)

        for entry in entries:
            line = f"{entry.author} ({entry.year}). {entry.title}. {entry.publisher}."
            p.drawString(50, y, line)
            y -= 20
            if y < 50:
                p.showPage()
                p.setFont("Helvetica", 11)
                y = height - 50

    if target_page in ["summary", "all"]:
        if y < 150:
            p.showPage()
            y = height - 50

        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Summary Overview")
        y -= 25
        p.setFont("Helvetica", 11)
        p.drawString(50, y, f"Total Selected Records: {entries.count()}")

    p.showPage()
    p.save()
    return response



# -------------------------------------------------------------------------------------------------
# DJANGO TEMPLATE TAGS
# -------------------------------------------------------------------------------------------------

register = template.Library()

@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        query[key] = value
    return query.urlencode()










