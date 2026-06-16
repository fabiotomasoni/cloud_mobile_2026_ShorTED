import 'package:flutter/material.dart';
import 'talk_repository.dart';
import 'models/talk.dart';

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MyTEDx',
      theme: ThemeData(
        primarySwatch: Colors.red,
      ),
      home: const MyHomePage(),
    );
  }
}

class MyHomePage extends StatefulWidget {
  const MyHomePage({super.key, this.title = 'MyTEDx'});

  final String title;

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  final TextEditingController _tagController = TextEditingController();
  final TextEditingController _idController = TextEditingController();

  late Future<List<Talk>> _tagTalks;
  late Future<List<Talk>> _idSearchTalks;

  int _currentTabIndex = 0; // 0 for Tag Search, 1 for ID Search
  int _tagPage = 1;
  int _idSearchPage = 1;
  bool _tagInit = true;
  bool _idInit = true;
  String _searchedTag = "";
  String _searchedId = "";

  // State variables for Talk detail screen (Watch Next)
  Talk? _selectedTalk;
  int _watchNextPage = 1;
  late Future<List<Talk>> _watchNextTalks;

  @override
  void initState() {
    super.initState();
    _tagTalks = initEmptyList();
    _idSearchTalks = initEmptyList();
    _watchNextTalks = initEmptyList();
  }

  void _getTalksByTag() {
    setState(() {
      _tagInit = false;
      _tagTalks = getTalksByTag(_searchedTag, _tagPage);
    });
  }

  void _getWatchNextSearch() {
    setState(() {
      _idInit = false;
      _idSearchTalks = getWatchNext(_searchedId);
    });
  }

  void _getWatchNextTalks() {
    if (_selectedTalk != null) {
      setState(() {
        _watchNextTalks = getWatchNext(_selectedTalk!.id);
      });
    }
  }

  void _selectTalk(Talk talk) {
    setState(() {
      _selectedTalk = talk;
      _watchNextPage = 1;
      _getWatchNextTalks();
    });
  }

  void _onTabTapped(int index) {
    if (index == _currentTabIndex) {
      // Tapping the active tab resets it to the search input screen
      setState(() {
        _selectedTalk = null;
        if (index == 0) {
          _tagInit = true;
          _tagPage = 1;
          _tagController.clear();
          _tagTalks = initEmptyList();
        } else {
          _idInit = true;
          _idSearchPage = 1;
          _idController.clear();
          _idSearchTalks = initEmptyList();
        }
      });
    } else {
      setState(() {
        _currentTabIndex = index;
        _selectedTalk = null;
      });
    }
  }

  String _getErrorMessage(Object? error) {
    if (error == null) return "Errore sconosciuto";
    final errorStr = error.toString();
    if (errorStr.startsWith("Exception: ")) {
      return errorStr.substring("Exception: ".length);
    }
    return errorStr;
  }

  Widget _buildPaginationBar({
    required int currentPage,
    int? totalPages,
    required bool hasItems,
    required VoidCallback? onPrevious,
    required VoidCallback? onNext,
  }) {
    final hasPrevious = currentPage > 1;
    final hasNext = totalPages != null ? currentPage < totalPages : hasItems;

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 16.0),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(8.0),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          ElevatedButton.icon(
            onPressed: hasPrevious ? onPrevious : null,
            icon: const Icon(Icons.arrow_back, size: 18),
            label: const Text('Prev'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            ),
          ),
          Text(
            totalPages != null ? 'Page $currentPage of $totalPages' : 'Page $currentPage',
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          ElevatedButton.icon(
            onPressed: hasNext ? onNext : null,
            icon: const Icon(Icons.arrow_forward, size: 18),
            label: const Text('Next'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTagInputScreen() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: <Widget>[
        const Text(
          'Search Talks by Tag',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.red),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _tagController,
          decoration: const InputDecoration(
            hintText: 'Enter tag (e.g. children, technology)',
            border: OutlineInputBorder(),
            prefixIcon: Icon(Icons.tag),
          ),
        ),
        const SizedBox(height: 16),
        ElevatedButton(
          style: ElevatedButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 12),
          ),
          child: const Text('Search by tag', style: TextStyle(fontSize: 16)),
          onPressed: () {
            setState(() {
              _searchedTag = _tagController.text;
              _tagPage = 1;
              _getTalksByTag();
            });
          },
        ),
      ],
    );
  }

  Widget _buildIdInputScreen() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: <Widget>[
        const Text(
          'Search Watch Next by Talk ID',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.red),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _idController,
          decoration: const InputDecoration(
            hintText: 'Enter talk ID (e.g. 10005, 53)',
            border: OutlineInputBorder(),
            prefixIcon: Icon(Icons.perm_identity),
          ),
          keyboardType: TextInputType.number,
        ),
        const SizedBox(height: 16),
        ElevatedButton(
          style: ElevatedButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 12),
          ),
          child: const Text('Search Watch Next', style: TextStyle(fontSize: 16)),
          onPressed: () {
            setState(() {
              _searchedId = _idController.text;
              _idSearchPage = 1;
              _getWatchNextSearch();
            });
          },
        ),
      ],
    );
  }

  Widget _buildTagResultsScreen() {
    return FutureBuilder<List<Talk>>(
      future: _tagTalks,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        } else if (snapshot.hasError) {
          return Column(
            children: [
              Text(
                "#$_searchedTag",
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: Center(
                  child: Text(
                    _getErrorMessage(snapshot.error),
                    style: const TextStyle(fontSize: 16, color: Colors.red, fontWeight: FontWeight.w500),
                  ),
                ),
              ),
              _buildPaginationBar(
                currentPage: _tagPage,
                hasItems: false,
                onPrevious: () {},
                onNext: () {},
              ),
            ],
          );
        } else if (snapshot.hasData) {
          final talks = snapshot.data!;

          if (talks.isEmpty) {
            return Column(
              children: [
                Text(
                  "#$_searchedTag",
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                const Expanded(
                  child: Center(
                    child: Text("No talks found on this page."),
                  ),
                ),
                _buildPaginationBar(
                  currentPage: _tagPage,
                  hasItems: false,
                  onPrevious: () {
                    setState(() {
                      _tagPage -= 1;
                      _getTalksByTag();
                    });
                  },
                  onNext: () {},
                ),
              ],
            );
          }

          return Column(
            children: [
              Text(
                "#$_searchedTag",
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: ListView.builder(
                  itemCount: talks.length,
                  itemBuilder: (context, index) {
                    final talk = talks[index];
                    final isEven = index % 2 == 0;

                    return Container(
                      color: isEven ? Colors.white : Colors.red.shade50,
                      child: ListTile(
                        subtitle: Text(talk.mainSpeaker),
                        title: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(talk.title, style: const TextStyle(fontWeight: FontWeight.bold)),
                            const SizedBox(height: 4),
                            Wrap(
                              spacing: 6,
                              children: talk.keyPhrases
                                  .map((k) => Chip(
                                        label: Text(k, style: const TextStyle(fontSize: 12)),
                                        backgroundColor: Colors.red.shade100,
                                      ))
                                  .toList(),
                            ),
                          ],
                        ),
                        onTap: () => _selectTalk(talk),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 8),
              _buildPaginationBar(
                currentPage: _tagPage,
                hasItems: talks.length == 6, // Tag search page size is 6
                onPrevious: () {
                  setState(() {
                    _tagPage -= 1;
                    _getTalksByTag();
                  });
                },
                onNext: () {
                  setState(() {
                    _tagPage += 1;
                    _getTalksByTag();
                  });
                },
              ),
            ],
          );
        }
        return const Center(child: CircularProgressIndicator());
      },
    );
  }

  Widget _buildIdResultsScreen() {
    return FutureBuilder<List<Talk>>(
      future: _idSearchTalks,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        } else if (snapshot.hasError) {
          return Column(
            children: [
              Text(
                "Watch Next for ID: $_searchedId",
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: Center(
                  child: Text(
                    _getErrorMessage(snapshot.error),
                    style: const TextStyle(fontSize: 16, color: Colors.red, fontWeight: FontWeight.w500),
                  ),
                ),
              ),
              _buildPaginationBar(
                currentPage: _idSearchPage,
                totalPages: 1,
                hasItems: false,
                onPrevious: () {},
                onNext: () {},
              ),
            ],
          );
        } else if (snapshot.hasData) {
          final talks = snapshot.data!;

          if (talks.isEmpty) {
            return Column(
              children: [
                Text(
                  "Watch Next for ID: $_searchedId",
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                const Expanded(
                  child: Center(
                    child: Text("No recommendations found on this page."),
                  ),
                ),
                _buildPaginationBar(
                  currentPage: _idSearchPage,
                  totalPages: 1,
                  hasItems: false,
                  onPrevious: () {},
                  onNext: () {},
                ),
              ],
            );
          }

          final itemsPerPage = 10;
          final totalItems = talks.length;
          final totalPages = (totalItems / itemsPerPage).ceil();

          final startIndex = (_idSearchPage - 1) * itemsPerPage;
          final endIndex = startIndex + itemsPerPage;
          final slicedTalks = talks.sublist(
            startIndex,
            endIndex > totalItems ? totalItems : endIndex,
          );

          return Column(
            children: [
              Text(
                "Watch Next for ID: $_searchedId",
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: ListView.builder(
                  itemCount: slicedTalks.length,
                  itemBuilder: (context, index) {
                    final talk = slicedTalks[index];
                    final isEven = index % 2 == 0;

                    return Container(
                      color: isEven ? Colors.white : Colors.red.shade50,
                      child: ListTile(
                        title: Text(talk.title, style: const TextStyle(fontWeight: FontWeight.bold)),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(talk.mainSpeaker),
                            const SizedBox(height: 4),
                            Text(
                              talk.details,
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey.shade600,
                              ),
                            ),
                          ],
                        ),
                        onTap: () => _selectTalk(talk),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 8),
              _buildPaginationBar(
                currentPage: _idSearchPage,
                totalPages: totalPages,
                hasItems: slicedTalks.isNotEmpty,
                onPrevious: () {
                  setState(() {
                    _idSearchPage -= 1;
                  });
                },
                onNext: () {
                  setState(() {
                    _idSearchPage += 1;
                  });
                },
              ),
            ],
          );
        }
        return const Center(child: CircularProgressIndicator());
      },
    );
  }

  Widget _buildTalkDetailScreen(Talk talk) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Main Talk Details card
        Card(
          elevation: 4,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          color: Colors.red.shade50,
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  talk.title,
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: Colors.red,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  talk.mainSpeaker.isNotEmpty ? "Speaker: ${talk.mainSpeaker}" : "No Speaker Info",
                  style: const TextStyle(
                    fontSize: 15,
                    fontStyle: FontStyle.italic,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  talk.details,
                  style: const TextStyle(fontSize: 14, height: 1.4),
                ),
                if (talk.url.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  InkWell(
                    onTap: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text("Link to video: ${talk.url}")),
                      );
                    },
                    child: Text(
                      talk.url,
                      style: const TextStyle(
                        color: Colors.blue,
                        decoration: TextDecoration.underline,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ]
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        const Text(
          "Watch Next:",
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: FutureBuilder<List<Talk>>(
            future: _watchNextTalks,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              } else if (snapshot.hasError) {
                return Column(
                  children: [
                    Expanded(
                      child: Center(
                        child: Text(
                          _getErrorMessage(snapshot.error),
                          style: const TextStyle(fontSize: 16, color: Colors.red, fontWeight: FontWeight.w500),
                        ),
                      ),
                    ),
                    _buildPaginationBar(
                      currentPage: _watchNextPage,
                      totalPages: 1,
                      hasItems: false,
                      onPrevious: () {},
                      onNext: () {},
                    ),
                  ],
                );
              } else if (snapshot.hasData) {
                final related = snapshot.data!;

                if (related.isEmpty) {
                  return Column(
                    children: [
                      const Expanded(
                        child: Center(
                          child: Text("No recommendations found on this page."),
                        ),
                      ),
                      _buildPaginationBar(
                        currentPage: _watchNextPage,
                        totalPages: 1,
                        hasItems: false,
                        onPrevious: () {},
                        onNext: () {},
                      ),
                    ],
                  );
                }

                final itemsPerPage = 10;
                final totalItems = related.length;
                final totalPages = (totalItems / itemsPerPage).ceil();

                final startIndex = (_watchNextPage - 1) * itemsPerPage;
                final endIndex = startIndex + itemsPerPage;
                final slicedRelated = related.sublist(
                  startIndex,
                  endIndex > totalItems ? totalItems : endIndex,
                );

                return Column(
                  children: [
                    Expanded(
                      child: ListView.builder(
                        itemCount: slicedRelated.length,
                        itemBuilder: (context, index) {
                          final item = slicedRelated[index];
                          final isEven = index % 2 == 0;
                          return Card(
                            elevation: 1,
                            margin: const EdgeInsets.symmetric(vertical: 4),
                            color: isEven ? Colors.white : Colors.red.shade50,
                            child: ListTile(
                              title: Text(
                                item.title,
                                style: const TextStyle(fontWeight: FontWeight.bold),
                              ),
                              subtitle: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(item.mainSpeaker),
                                  const SizedBox(height: 4),
                                  Text(
                                    item.details,
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.grey.shade600,
                                    ),
                                  ),
                                ],
                              ),
                              onTap: () => _selectTalk(item),
                            ),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 8),
                    _buildPaginationBar(
                      currentPage: _watchNextPage,
                      totalPages: totalPages,
                      hasItems: slicedRelated.isNotEmpty,
                      onPrevious: () {
                        setState(() {
                          _watchNextPage -= 1;
                        });
                      },
                      onNext: () {
                        setState(() {
                          _watchNextPage += 1;
                        });
                      },
                    ),
                  ],
                );
              }
              return const Center(child: CircularProgressIndicator());
            },
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    String appBarTitle = 'My TEDx App';
    if (_selectedTalk != null) {
      appBarTitle = 'Talk Details';
    } else if (_currentTabIndex == 0) {
      appBarTitle = 'Tag Search';
    } else {
      appBarTitle = 'ID Recommendations Search';
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(appBarTitle),
        leading: _selectedTalk != null
            ? IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () {
                  setState(() {
                    _selectedTalk = null;
                  });
                },
              )
            : null,
      ),
      body: Padding(
        padding: const EdgeInsets.all(8.0),
        child: _selectedTalk != null
            ? _buildTalkDetailScreen(_selectedTalk!)
            : _currentTabIndex == 0
                ? (_tagInit ? _buildTagInputScreen() : _buildTagResultsScreen())
                : (_idInit ? _buildIdInputScreen() : _buildIdResultsScreen()),
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentTabIndex,
        onTap: _onTabTapped,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.tag),
            label: 'Tag Search',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.recommend),
            label: 'ID Search',
          ),
        ],
      ),
    );
  }
}