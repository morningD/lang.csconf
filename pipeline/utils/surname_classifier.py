"""Lightweight rule-based name classifier using surname/given-name patterns.

No ML dependencies needed. Covers the major language groups with reasonable accuracy.
"""

# Common Chinese surnames (covers ~85% of Chinese population)
CHINESE_SURNAMES = {
    'wang', 'li', 'zhang', 'liu', 'chen', 'yang', 'huang', 'zhao', 'wu', 'zhou',
    'xu', 'sun', 'ma', 'zhu', 'hu', 'guo', 'he', 'lin', 'luo', 'gao',
    'zheng', 'liang', 'xie', 'tang', 'han', 'cao', 'deng', 'xiao', 'feng', 'zeng',
    'cheng', 'cai', 'peng', 'pan', 'yuan', 'yu', 'dong', 'lu', 'su', 'ye',
    'ren', 'wei', 'jiang', 'du', 'ding', 'shen', 'fan', 'song', 'wan', 'tian',
    'jin', 'qin', 'dai', 'xia', 'fu', 'shi', 'gu', 'meng', 'bai', 'qiu',
    'hou', 'shao', 'xiong', 'lv', 'cui', 'tan', 'long', 'kong', 'kang', 'mao',
    'qiang', 'wen', 'yan', 'jia', 'zou', 'duan', 'lei', 'hao', 'yi', 'mo',
    'chang', 'lian', 'lai', 'nie', 'yao', 'ping', 'yue', 'xiang', 'min', 'niu',
    'ai', 'bi', 'shan', 'qi', 'ji', 'liao', 'gong', 'ning', 'ruan', 'tao',
    'xing', 'quan', 'he', 'sang', 'yun', 'nan', 'que', 'gan',
    # Pinyin variants with common romanizations
    'tsai', 'hsieh', 'chiang', 'tseng', 'hsiao', 'hsü', 'chou',
}

# Chinese given name patterns (Pinyin-like syllable patterns)
CHINESE_SYLLABLES = {
    'ao', 'bai', 'ban', 'bang', 'bao', 'bei', 'ben', 'biao', 'bin', 'bing',
    'bo', 'cai', 'can', 'cang', 'cao', 'ce', 'cen', 'chai', 'chan', 'chang',
    'chao', 'chen', 'cheng', 'chi', 'chong', 'chu', 'chuan', 'chuang', 'chui',
    'chun', 'ci', 'cong', 'cui', 'cun', 'da', 'dai', 'dan', 'dao', 'de',
    'deng', 'di', 'dian', 'diao', 'die', 'ding', 'dong', 'dou', 'du', 'duan',
    'dui', 'dun', 'duo', 'en', 'er', 'fan', 'fang', 'fei', 'fen', 'feng',
    'fo', 'fou', 'fu', 'gai', 'gan', 'gang', 'gao', 'ge', 'gei', 'gen',
    'geng', 'gong', 'gou', 'gu', 'gua', 'guai', 'guan', 'guang', 'gui', 'gun',
    'guo', 'hai', 'han', 'hang', 'hao', 'hei', 'hen', 'heng', 'hong', 'hou',
    'hu', 'hua', 'huai', 'huan', 'huang', 'hui', 'hun', 'huo', 'ji', 'jia',
    'jian', 'jiang', 'jiao', 'jie', 'jin', 'jing', 'jiong', 'jiu', 'ju', 'juan',
    'jue', 'jun', 'kai', 'kan', 'kang', 'kao', 'ke', 'ken', 'keng', 'kong',
    'kou', 'ku', 'kua', 'kuai', 'kuan', 'kuang', 'kui', 'kun', 'kuo', 'lai',
    'lan', 'lang', 'lao', 'lei', 'leng', 'li', 'lia', 'lian', 'liang', 'liao',
    'lie', 'lin', 'ling', 'liu', 'long', 'lou', 'lu', 'luan', 'lun', 'luo',
    'mai', 'man', 'mang', 'mao', 'mei', 'men', 'meng', 'mi', 'mian', 'miao',
    'min', 'ming', 'mo', 'mou', 'mu', 'na', 'nai', 'nan', 'nang', 'nao',
    'nei', 'nen', 'neng', 'ni', 'nian', 'niang', 'niao', 'nie', 'nin', 'ning',
    'niu', 'nong', 'nu', 'nuan', 'nuo', 'ou', 'pai', 'pan', 'pang', 'pao',
    'pei', 'pen', 'peng', 'pi', 'pian', 'piao', 'pie', 'pin', 'ping', 'po',
    'pou', 'pu', 'qi', 'qia', 'qian', 'qiang', 'qiao', 'qie', 'qin', 'qing',
    'qiong', 'qiu', 'qu', 'quan', 'que', 'qun', 'ran', 'rang', 'rao', 'ren',
    'reng', 'ri', 'rong', 'rou', 'ru', 'ruan', 'rui', 'run', 'ruo', 'sai',
    'san', 'sang', 'sao', 'sen', 'seng', 'sha', 'shan', 'shang', 'shao', 'she',
    'shen', 'sheng', 'shi', 'shou', 'shu', 'shua', 'shuai', 'shuan', 'shuang',
    'shui', 'shun', 'shuo', 'si', 'song', 'sou', 'su', 'suan', 'sui', 'sun',
    'suo', 'ta', 'tai', 'tan', 'tang', 'tao', 'te', 'teng', 'ti', 'tian',
    'tiao', 'tie', 'ting', 'tong', 'tou', 'tu', 'tuan', 'tui', 'tun', 'tuo',
    'wa', 'wai', 'wan', 'wang', 'wei', 'wen', 'weng', 'wo', 'wu', 'xi', 'xia',
    'xian', 'xiang', 'xiao', 'xie', 'xin', 'xing', 'xiong', 'xiu', 'xu', 'xuan',
    'xue', 'xun', 'ya', 'yan', 'yang', 'yao', 'ye', 'yi', 'yin', 'ying',
    'yong', 'you', 'yu', 'yuan', 'yue', 'yun', 'za', 'zai', 'zan', 'zang',
    'zao', 'ze', 'zei', 'zen', 'zeng', 'zha', 'zhai', 'zhan', 'zhang', 'zhao',
    'zhe', 'zhen', 'zheng', 'zhi', 'zhong', 'zhou', 'zhu', 'zhua', 'zhuai',
    'zhuan', 'zhuang', 'zhui', 'zhun', 'zhuo', 'zi', 'zong', 'zou', 'zu',
    'zuan', 'zui', 'zun', 'zuo',
}

# Korean surnames
KOREAN_SURNAMES = {
    'kim', 'lee', 'park', 'choi', 'jung', 'kang', 'cho', 'yoon', 'jang',
    'lim', 'han', 'oh', 'seo', 'shin', 'kwon', 'hwang', 'ahn', 'song',
    'yoo', 'hong', 'jeon', 'ko', 'moon', 'yang', 'son', 'bae', 'baek',
    'heo', 'nam', 'yun', 'noh', 'ha', 'kwak', 'sung', 'ryu', 'chung',
    'min', 'woo', 'ji', 'eom', 'cha', 'byun', 'sim', 'roh', 'hyun',
    'yeom', 'jeong', 'im',
    # Note: Lee, Park, Yang, Song overlap with English/Chinese but Korean
    # context determined by given name patterns
}

# Korean given name patterns (common syllables)
KOREAN_GIVEN_PATTERNS = {
    'hyun', 'joon', 'jun', 'soo', 'min', 'young', 'hee', 'jin', 'woo',
    'sung', 'hyung', 'kyung', 'dong', 'won', 'hwan', 'eun', 'seung',
    'yeon', 'gyeong', 'byeong', 'kwang', 'joong', 'myung', 'chul',
    'hoon', 'bong', 'ho', 'geun', 'sang', 'yeong', 'tae',
}

# Japanese surnames
JAPANESE_SURNAMES = {
    'sato', 'suzuki', 'takahashi', 'tanaka', 'watanabe', 'ito', 'yamamoto',
    'nakamura', 'kobayashi', 'kato', 'yoshida', 'yamada', 'sasaki', 'yamazaki',
    'matsumoto', 'inoue', 'kimura', 'hayashi', 'shimizu', 'yamaguchi',
    'saito', 'mori', 'ikeda', 'hashimoto', 'abe', 'ishikawa', 'yamashita',
    'ogawa', 'ishii', 'hasegawa', 'okada', 'goto', 'maeda', 'fujita',
    'endo', 'aoki', 'sakamoto', 'murakami', 'fukuda', 'ota', 'miura',
    'fujii', 'okamoto', 'matsuda', 'nakajima', 'fujiwara', 'nishimura',
    'ono', 'sugiyama', 'arai', 'takagi', 'noda', 'kaneko', 'wada',
    'ueda', 'morimoto', 'hara', 'takeuchi', 'kawaguchi', 'miyazaki',
    'honda', 'nishida', 'otsuka', 'ueno', 'tamura', 'kubo', 'kojima',
    'chiba', 'iwasaki', 'sakurai', 'kinoshita', 'noguchi', 'matsui',
    'nomura', 'kikuchi', 'sano', 'onishi', 'sugawara', 'mizuno', 'nagai',
    'kudo', 'tsuji', 'oishi', 'hamada', 'murata', 'yano', 'ishida',
    'naito', 'takeda', 'kawai', 'shimada', 'taniguchi', 'iida',
    'nakanishi', 'hirata', 'tsuchiya', 'osawa', 'miyamoto', 'kurosawa',
    'morita', 'nishikawa', 'otani', 'makino', 'higuchi', 'iwata', 'ozaki',
}

# Indian surnames (common ones)
INDIAN_SURNAMES = {
    'sharma', 'kumar', 'singh', 'patel', 'gupta', 'reddy', 'das', 'nair',
    'menon', 'iyer', 'rao', 'joshi', 'mishra', 'agarwal', 'mehta', 'shah',
    'verma', 'pandey', 'saxena', 'srivastava', 'trivedi', 'bhatt', 'desai',
    'chopra', 'malhotra', 'kapoor', 'bhatia', 'chauhan', 'thakur', 'pillai',
    'mukherjee', 'banerjee', 'chatterjee', 'ghosh', 'bose', 'dutta',
    'sengupta', 'majumdar', 'ganguly', 'chakraborty', 'bhattacharya',
    'sinha', 'prasad', 'choudhury', 'jain', 'rastogi', 'bajaj', 'goyal',
    'arora', 'aggarwal', 'sethi', 'bedi', 'rajan', 'naidu', 'babu',
    'krishnan', 'subramaniam', 'ramesh', 'venkatesh', 'mohan', 'ravi',
    'anand', 'mahajan', 'patil', 'tiwari', 'dubey', 'shukla', 'dwivedi',
    'hegde', 'kamath', 'kulkarni', 'deshpande', 'pawar', 'shinde',
    'jadhav', 'gaikwad', 'chavan',
}

# Vietnamese surnames
VIETNAMESE_SURNAMES = {
    'nguyen', 'tran', 'le', 'pham', 'hoang', 'huynh', 'phan', 'vu', 'vo',
    'dang', 'bui', 'do', 'ho', 'ngo', 'duong', 'ly', 'truong', 'dinh',
    'luong', 'ta', 'luu', 'dao', 'mai', 'trinh', 'tong', 'lam', 'thai',
}

# German surnames
GERMAN_SURNAMES = {
    'mueller', 'muller', 'schmidt', 'schneider', 'fischer', 'weber', 'meyer',
    'wagner', 'becker', 'schulz', 'hoffmann', 'schaefer', 'koch', 'bauer',
    'richter', 'klein', 'wolf', 'schroeder', 'neumann', 'schwarz',
    'zimmermann', 'braun', 'krueger', 'hofmann', 'hartmann', 'lange',
    'schmitt', 'werner', 'schmitz', 'krause', 'meier', 'lehmann',
    'koenig', 'walter', 'huber', 'fuchs', 'kaiser', 'scholz', 'wirth',
    'haas', 'jung', 'hahn', 'schubert', 'vogt', 'friedrich', 'keller',
    'guenther', 'frank', 'berger', 'roth', 'beck', 'lorenz', 'baumann',
    'franke', 'albrecht', 'schuster', 'simon', 'ludwig', 'boehm', 'winter',
    'kraus', 'martin', 'schumacher', 'vogel', 'seidel', 'stein',
}

# French surnames
FRENCH_SURNAMES = {
    'martin', 'bernard', 'dubois', 'thomas', 'robert', 'richard', 'petit',
    'durand', 'leroy', 'moreau', 'simon', 'laurent', 'lefebvre', 'michel',
    'garcia', 'david', 'bertrand', 'roux', 'vincent', 'fournier', 'morel',
    'girard', 'andre', 'lefevre', 'mercier', 'dupont', 'lambert', 'bonnet',
    'francois', 'martinez', 'legrand', 'garnier', 'faure', 'rousseau',
    'blanc', 'guerin', 'muller', 'henry', 'roussel', 'nicolas', 'perrin',
    'morin', 'mathieu', 'clement', 'gauthier', 'dumont', 'lopez', 'fontaine',
    'chevalier', 'robin', 'masson', 'sanchez', 'gerard', 'nguyen',
    'boyer', 'denis', 'lemaire', 'duval', 'joly', 'beaumont', 'riviere',
    'leclerc', 'benoit', 'picard', 'marchand', 'dufour', 'blanchard',
}

# Spanish/Portuguese surnames
SPANISH_SURNAMES = {
    'garcia', 'rodriguez', 'martinez', 'lopez', 'gonzalez', 'hernandez',
    'perez', 'sanchez', 'ramirez', 'torres', 'flores', 'rivera', 'gomez',
    'diaz', 'reyes', 'cruz', 'morales', 'ortiz', 'gutierrez', 'chavez',
    'ramos', 'vargas', 'castillo', 'jimenez', 'moreno', 'romero', 'herrera',
    'medina', 'aguilar', 'garza', 'castro', 'vazquez', 'ruiz', 'alvarez',
    'mendoza', 'guzman', 'fernandez', 'munoz', 'silva', 'santos',
    'costa', 'ferreira', 'oliveira', 'sousa', 'souza', 'pereira', 'lima',
    'carvalho', 'almeida', 'ribeiro', 'nascimento', 'araujo', 'cardoso',
    'melo', 'barbosa', 'rocha', 'correia', 'dias', 'monteiro', 'teixeira',
}

# Italian surnames
ITALIAN_SURNAMES = {
    'rossi', 'russo', 'ferrari', 'esposito', 'bianchi', 'romano', 'colombo',
    'ricci', 'marino', 'greco', 'bruno', 'gallo', 'conti', 'costa', 'giordano',
    'mancini', 'rizzo', 'lombardi', 'moretti', 'barbieri', 'fontana', 'santoro',
    'mariani', 'rinaldi', 'caruso', 'ferrara', 'galli', 'martini', 'leone',
    'longo', 'gentile', 'martinelli', 'vitale', 'lombardo', 'serra', 'coppola',
    'de luca', 'damico', 'marchetti', 'parisi', 'villa', 'conte', 'ferri',
    'fabbri', 'orlando', 'cattaneo', 'pellegrini', 'palumbo', 'bernardi',
}

# Persian/Arabic surnames
PERSIAN_SURNAMES = {
    'mohammadi', 'hosseini', 'rezaei', 'kazemi', 'ahmadi', 'hashemi', 'moradi',
    'karimi', 'mousavi', 'rahimi', 'jafari', 'hajizadeh', 'taheri', 'ghorbani',
    'nazari', 'alirezaei', 'sadeghi', 'bagheri', 'ebrahimi', 'safari',
    'nouri', 'nikkhah', 'esmaili', 'khosravi', 'rostami', 'lotfi',
    'al-', 'el-', 'abdul', 'mohammed', 'ahmed', 'ali', 'hassan', 'hussein',
    'ibrahim', 'khalil', 'omar', 'saleh', 'youssef', 'nasser', 'mansour',
    'ismail', 'sultan', 'karim', 'farid',
}

# Turkish surnames
TURKISH_SURNAMES = {
    'yilmaz', 'kaya', 'demir', 'celik', 'sahin', 'yildiz', 'yildirim',
    'ozturk', 'aydin', 'ozdemir', 'arslan', 'dogan', 'kilic', 'aslan',
    'cetin', 'kara', 'koc', 'kurt', 'ozkan', 'simsek', 'polat',
    'korkmaz', 'karatas', 'aksoy', 'cinar', 'unal', 'erdogan', 'bulut',
    'basar', 'tekin', 'acar', 'gul', 'toprak', 'eryilmaz', 'bayrak',
}

# Russian/Eastern European surnames
RUSSIAN_SURNAMES = {
    'ivanov', 'smirnov', 'kuznetsov', 'popov', 'vasiliev', 'petrov',
    'sokolov', 'mikhailov', 'novikov', 'fedorov', 'morozov', 'volkov',
    'alekseev', 'lebedev', 'semenov', 'egorov', 'pavlov', 'kozlov',
    'stepanov', 'nikolaev', 'orlov', 'andreev', 'makarov', 'nikitin',
    'zakharov', 'zaitsev', 'soloviev', 'borisov', 'yakovlev', 'grigoryev',
    'romanov', 'voronov', 'kovalev', 'belov', 'medvedev', 'antonov',
    'tarasov', 'zhukov', 'baranov', 'filatov', 'komarov', 'titov',
}


def _is_chinese_name(parts: list[str]) -> float:
    """Score how likely a name is Chinese. Returns 0.0-1.0."""
    last = parts[-1].lower()
    first_parts = [p.lower() for p in parts[:-1]]

    score = 0.0

    # Check surname
    if last in CHINESE_SURNAMES:
        score += 0.5

    # Check if given name parts look like pinyin
    for fp in first_parts:
        if fp in CHINESE_SYLLABLES:
            score += 0.3
        # Check if it's two pinyin syllables concatenated (e.g., "yuanmin", "zixuan")
        elif len(fp) > 3:
            for i in range(2, len(fp)):
                if fp[:i] in CHINESE_SYLLABLES and fp[i:] in CHINESE_SYLLABLES:
                    score += 0.35
                    break

    return min(score, 1.0)


def _is_korean_name(parts: list[str]) -> float:
    """Score how likely a name is Korean."""
    last = parts[-1].lower()
    given = ' '.join(parts[:-1]).lower() if len(parts) > 1 else ''

    score = 0.0
    if last in KOREAN_SURNAMES:
        score += 0.4

    # Korean given names often have specific patterns
    for pattern in KOREAN_GIVEN_PATTERNS:
        if pattern in given:
            score += 0.3
            break

    # Hyphenated given names are very Korean (e.g., "Hyun-Joon")
    if any('-' in p for p in parts[:-1]):
        score += 0.2

    return min(score, 1.0)


def _is_japanese_name(parts: list[str]) -> float:
    """Score how likely a name is Japanese."""
    last = parts[-1].lower()
    score = 0.0
    if last in JAPANESE_SURNAMES:
        score += 0.7
    return min(score, 1.0)


def _check_surname_set(parts: list[str], surname_set: set, lang: str) -> tuple[str, float]:
    """Generic surname check."""
    last = parts[-1].lower()
    if last in surname_set:
        return lang, 0.6
    # Check for prefix matches (e.g., "al-" for Arabic)
    if lang in ('Arabic', 'Persian'):
        for prefix in ('al-', 'el-'):
            if last.startswith(prefix):
                return lang, 0.6
    return '', 0.0


def classify_name_rule(name: str) -> dict:
    """Classify a name into a language group using surname/given-name pattern rules.

    Returns dict with: name, nationality, language, confidence
    """
    parts = name.strip().split()
    if not parts:
        return {'name': name, 'nationality': 'Unknown', 'language': 'Other', 'confidence': 0.0}

    # Score each language
    scores: dict[str, float] = {}

    # Chinese
    scores['Chinese'] = _is_chinese_name(parts)

    # Korean
    scores['Korean'] = _is_korean_name(parts)

    # Japanese
    scores['Japanese'] = _is_japanese_name(parts)

    # Indian
    _, s = _check_surname_set(parts, INDIAN_SURNAMES, 'Indian')
    scores['Indian'] = s

    # Vietnamese
    _, s = _check_surname_set(parts, VIETNAMESE_SURNAMES, 'Vietnamese')
    scores['Vietnamese'] = s

    # German
    _, s = _check_surname_set(parts, GERMAN_SURNAMES, 'German')
    scores['German'] = s

    # French
    _, s = _check_surname_set(parts, FRENCH_SURNAMES, 'French')
    scores['French'] = s

    # Spanish
    _, s = _check_surname_set(parts, SPANISH_SURNAMES, 'Spanish')
    scores['Spanish'] = s

    # Italian
    _, s = _check_surname_set(parts, ITALIAN_SURNAMES, 'Italian')
    scores['Italian'] = s

    # Russian
    _, s = _check_surname_set(parts, RUSSIAN_SURNAMES, 'Russian')
    scores['Russian'] = s
    # Slavic surname patterns
    last = parts[-1].lower()
    if last.endswith(('ov', 'ev', 'ova', 'eva', 'sky', 'ski', 'skiy', 'enko', 'uk', 'chuk')):
        scores['Russian'] = max(scores.get('Russian', 0), 0.5)

    # Persian/Arabic
    _, s = _check_surname_set(parts, PERSIAN_SURNAMES, 'Persian')
    scores['Persian'] = s
    if last.endswith(('zadeh', 'pour', 'nejad', 'khah')):
        scores['Persian'] = max(scores.get('Persian', 0), 0.7)

    # Turkish
    _, s = _check_surname_set(parts, TURKISH_SURNAMES, 'Turkish')
    scores['Turkish'] = s
    if last.endswith(('oglu', 'oğlu')):
        scores['Turkish'] = max(scores.get('Turkish', 0), 0.6)

    # Find best match
    best_lang = max(scores, key=scores.get)
    best_score = scores[best_lang]

    if best_score < 0.4:
        # Default to English for Western-style names without strong signals
        return {
            'name': name,
            'nationality': 'Unknown',
            'language': 'English',
            'confidence': 0.3,
        }

    return {
        'name': name,
        'nationality': best_lang,
        'language': best_lang,
        'confidence': round(best_score, 2),
    }
